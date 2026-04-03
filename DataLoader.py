"""
DataLoader.py
Connects to AWS S3, lists patient folders under Old_PACS/,
randomly selects 600 patients, and downloads:
  - DICOM files from the M1_ series with the most files
  - XML report(s) from the S1_ folder
  - .doc report(s) from the R1_ folder
"""

import os
import sys
import csv
import random
import boto3
from botocore.config import Config
from dotenv import load_dotenv

# ============================================================
# AWS CREDENTIALS — Loaded from .env file (never commit .env)
# ============================================================
load_dotenv()  # reads .env file in the same directory

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY or not AWS_REGION:
    print("ERROR: AWS credentials not found.")
    print("Create a .env file in the same folder as this script with:")
    print('  AWS_ACCESS_KEY_ID=your_key')
    print('  AWS_SECRET_ACCESS_KEY=your_secret')
    print('  AWS_REGION=your_region')
    print("See .env.example for a template.")
    sys.exit(1)

# ============================================================
# CONFIGURATION
# ============================================================
BUCKET_NAME = "bioanalytixdata"
S3_PREFIX = "Orasis_Project/CT_Brain_Scans/G.H.Larissa/Dicom_Files/Old_PACS/"
NUM_PATIENTS = 600
LOCAL_OUTPUT_DIR = r"C:\Users\user\Desktop\Labels_orasis\downloaded_data"


def create_s3_client():
    """Create and return a boto3 S3 client with the configured credentials."""
    session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )
    return session.client("s3", config=Config(max_pool_connections=25))


def list_s3_common_prefixes(s3_client, bucket, prefix):
    """List all 'subdirectories' (common prefixes) under a given S3 prefix."""
    prefixes = []
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for cp in page.get("CommonPrefixes", []):
            prefixes.append(cp["Prefix"])
    return prefixes


def list_s3_objects(s3_client, bucket, prefix):
    """List all object keys under a given S3 prefix (non-recursive)."""
    keys = []
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def get_folder_name(prefix):
    """Extract the last folder name from an S3 prefix path.
    e.g. 'a/b/c/' -> 'c'
    """
    return prefix.rstrip("/").split("/")[-1]


def discover_patient_data(s3_client, patient_prefix):
    """
    For a patient folder, discover:
      - The S1_ study folder
      - The M1_ series folder with the most DICOM files
      - Any XML files in the S1_ folder
      - Any .doc files inside R1_ folders
    Returns a dict with the discovered paths or None on failure.
    """
    # Find S1_ study folder
    study_folders = [
        p for p in list_s3_common_prefixes(s3_client, BUCKET_NAME, patient_prefix)
        if get_folder_name(p).startswith("S1_")
    ]

    if not study_folders:
        return None

    study_prefix = study_folders[0]  # One S1_ per patient

    # List subfolders and files inside the S1_ folder
    s1_subfolders = list_s3_common_prefixes(s3_client, BUCKET_NAME, study_prefix)
    s1_files = list_s3_objects(s3_client, BUCKET_NAME, study_prefix)

    # Find M1_ series folders and pick the one with the most DICOM files
    m1_folders = [p for p in s1_subfolders if get_folder_name(p).startswith("M1_")]

    best_m1_prefix = None
    best_m1_count = 0
    best_m1_keys = []

    for m1_prefix in m1_folders:
        dicom_keys = list_s3_objects(s3_client, BUCKET_NAME, m1_prefix)
        if len(dicom_keys) > best_m1_count:
            best_m1_count = len(dicom_keys)
            best_m1_prefix = m1_prefix
            best_m1_keys = dicom_keys

    # Find XML files directly in S1_ folder
    xml_keys = [k for k in s1_files if k.lower().endswith(".xml")]

    # Find R1_ folders and .doc files inside them
    r1_folders = [p for p in s1_subfolders if get_folder_name(p).startswith("R1_")]
    doc_keys = []
    for r1_prefix in r1_folders:
        r1_files = list_s3_objects(s3_client, BUCKET_NAME, r1_prefix)
        doc_keys.extend([k for k in r1_files if k.lower().endswith((".doc", ".docx"))])

    return {
        "study_prefix": study_prefix,
        "best_m1_prefix": best_m1_prefix,
        "dicom_keys": best_m1_keys,
        "dicom_count": best_m1_count,
        "xml_keys": xml_keys,
        "doc_keys": doc_keys,
    }


def download_file(s3_client, bucket, key, local_path):
    """Download a single file from S3 to a local path."""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    s3_client.download_file(bucket, key, local_path)


def download_patient(s3_client, patient_prefix, patient_data, index, total):
    """Download all data for a single patient to the local output directory."""
    patient_id = get_folder_name(patient_prefix)
    patient_dir = os.path.join(LOCAL_OUTPUT_DIR, patient_id)
    dicoms_dir = os.path.join(patient_dir, "dicoms")
    reports_dir = os.path.join(patient_dir, "reports")
    os.makedirs(dicoms_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    # Download DICOM files
    dicom_count = 0
    for key in patient_data["dicom_keys"]:
        filename = key.split("/")[-1]
        local_path = os.path.join(dicoms_dir, filename)
        download_file(s3_client, BUCKET_NAME, key, local_path)
        dicom_count += 1

    # Download XML reports
    xml_count = 0
    for key in patient_data["xml_keys"]:
        filename = key.split("/")[-1]
        local_path = os.path.join(reports_dir, filename)
        download_file(s3_client, BUCKET_NAME, key, local_path)
        xml_count += 1

    # Download .doc reports
    doc_count = 0
    for key in patient_data["doc_keys"]:
        filename = key.split("/")[-1]
        local_path = os.path.join(reports_dir, filename)
        download_file(s3_client, BUCKET_NAME, key, local_path)
        doc_count += 1

    print(
        f"[{index}/{total}] {patient_id} — "
        f"{dicom_count} DICOMs, {xml_count} XML, {doc_count} DOC"
    )

    return {
        "patient_id": patient_id,
        "dicom_count": dicom_count,
        "xml_count": xml_count,
        "doc_count": doc_count,
        "has_report": (xml_count + doc_count) > 0,
        "s3_study_path": patient_data["study_prefix"],
        "s3_series_path": patient_data["best_m1_prefix"] or "",
    }


def save_manifest(results):
    """Save a CSV manifest of all downloaded patients."""
    manifest_path = os.path.join(LOCAL_OUTPUT_DIR, "manifest.csv")
    fieldnames = [
        "patient_id",
        "dicom_count",
        "xml_count",
        "doc_count",
        "has_report",
        "s3_study_path",
        "s3_series_path",
    ]
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\nManifest saved to: {manifest_path}")


def main():
    print("=" * 60)
    print("S3 CT Brain Scan DataLoader")
    print("=" * 60)

    # --- Phase 1: Connect to S3 ---
    print("\nConnecting to S3...")
    s3_client = create_s3_client()

    # --- Phase 2: List and sample patients ---
    print(f"Listing patients under: s3://{BUCKET_NAME}/{S3_PREFIX}")
    all_patient_prefixes = [
        p for p in list_s3_common_prefixes(s3_client, BUCKET_NAME, S3_PREFIX)
        if get_folder_name(p).startswith("P")
    ]
    total_available = len(all_patient_prefixes)
    print(f"Found {total_available} patient folders.")

    if total_available == 0:
        print("ERROR: No patient folders found. Check S3 path and credentials.")
        return

    if total_available < NUM_PATIENTS:
        print(
            f"WARNING: Only {total_available} patients available, "
            f"fewer than the requested {NUM_PATIENTS}. Using all."
        )
        selected_prefixes = all_patient_prefixes
    else:
        selected_prefixes = random.sample(all_patient_prefixes, NUM_PATIENTS)

    num_selected = len(selected_prefixes)
    print(f"Selected {num_selected} patients for download.\n")

    # --- Phase 3 & 4: Discover data and download ---
    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
    results = []
    skipped = []

    for i, patient_prefix in enumerate(selected_prefixes, start=1):
        patient_id = get_folder_name(patient_prefix)

        try:
            patient_data = discover_patient_data(s3_client, patient_prefix)

            if patient_data is None:
                print(f"[{i}/{num_selected}] {patient_id} — SKIPPED (no S1_ study folder)")
                skipped.append(patient_id)
                continue

            if patient_data["best_m1_prefix"] is None:
                print(f"[{i}/{num_selected}] {patient_id} — SKIPPED (no M1_ series folder)")
                skipped.append(patient_id)
                continue

            result = download_patient(s3_client, patient_prefix, patient_data, i, num_selected)
            results.append(result)

        except Exception as e:
            print(f"[{i}/{num_selected}] {patient_id} — ERROR: {e}")
            skipped.append(patient_id)

    # --- Phase 5: Summary ---
    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    total_dicoms = sum(r["dicom_count"] for r in results)
    total_xml = sum(r["xml_count"] for r in results)
    total_doc = sum(r["doc_count"] for r in results)
    patients_with_reports = sum(1 for r in results if r["has_report"])
    patients_without_reports = sum(1 for r in results if not r["has_report"])

    print(f"Patients downloaded:      {len(results)}")
    print(f"Patients skipped:         {len(skipped)}")
    print(f"Total DICOM files:        {total_dicoms}")
    print(f"Total XML reports:        {total_xml}")
    print(f"Total DOC reports:        {total_doc}")
    print(f"Patients WITH report:     {patients_with_reports}")
    print(f"Patients WITHOUT report:  {patients_without_reports}")
    print(f"Output directory:         {LOCAL_OUTPUT_DIR}")

    if skipped:
        print(f"\nSkipped patients: {', '.join(skipped)}")

    # Save manifest CSV
    if results:
        save_manifest(results)

    print("\nDone.")


if __name__ == "__main__":
    main()
