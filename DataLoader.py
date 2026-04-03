"""
DataLoader.py
Reads selected_cases.csv (produced by QueryDB.py), then for each case:
  - Derives the S1_ study path from the s3_path (which points to R1_)
  - Finds the M1_ series folder with the most DICOM files
  - Downloads DICOMs + XML reports from S1_ + .doc reports from R1_
"""

import os
import sys
import csv
import boto3
from botocore.config import Config
from dotenv import load_dotenv

# ============================================================
# AWS CREDENTIALS — Loaded from .env file (never commit .env)
# ============================================================
load_dotenv()

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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, "selected_cases.csv")
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


def discover_patient_data(s3_client, s3_path):
    """
    Given an s3_path that points to a R1_ folder, discover:
      - The S1_ study folder (parent of R1_)
      - The M1_ series folder with the most DICOM files
      - Any XML files in the S1_ folder
      - Any .doc files inside the R1_ folder
    Returns a dict with the discovered paths or None on failure.
    """
    # s3_path points to R1_ folder, e.g.:
    # Orasis_Project/.../Old_PACS/P109259/S1_.../R1_...
    # Derive the S1_ study prefix (parent directory)
    r1_prefix = s3_path.rstrip("/") + "/"
    study_prefix = "/".join(s3_path.rstrip("/").split("/")[:-1]) + "/"

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

    # Find .doc files inside the R1_ folder (from the s3_path)
    doc_keys = []
    r1_files = list_s3_objects(s3_client, BUCKET_NAME, r1_prefix)
    doc_keys.extend([k for k in r1_files if k.lower().endswith((".doc", ".docx"))])

    return {
        "study_prefix": study_prefix,
        "r1_prefix": r1_prefix,
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


def download_patient(s3_client, patient_id, patient_data, anomaly_type, index, total):
    """Download all data for a single patient to the local output directory."""
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
        "anomaly_type": anomaly_type,
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
        "anomaly_type",
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

    # --- Phase 1: Read CSV produced by QueryDB.py ---
    if not os.path.exists(INPUT_CSV):
        print(f"ERROR: Input CSV not found: {INPUT_CSV}")
        print("Run QueryDB.py first to generate selected_cases.csv.")
        sys.exit(1)

    print(f"\nReading cases from: {INPUT_CSV}")
    cases = []
    with open(INPUT_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(row)

    if not cases:
        print("ERROR: CSV file is empty.")
        sys.exit(1)

    num_cases = len(cases)
    print(f"Loaded {num_cases} cases from CSV.\n")

    # --- Phase 2: Connect to S3 ---
    print("Connecting to S3...")
    s3_client = create_s3_client()

    # --- Phase 3: Discover data and download ---
    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
    results = []
    skipped = []

    for i, case in enumerate(cases, start=1):
        scan_id = case["scan_id"]
        patient_id = case["patient_id"]
        s3_path = case["s3_path"]
        anomaly_type = case["anomaly_type"]

        try:
            patient_data = discover_patient_data(s3_client, s3_path)

            if patient_data is None:
                print(f"[{i}/{num_cases}] {patient_id} (scan {scan_id}) — SKIPPED (could not find study folder)")
                skipped.append(patient_id)
                continue

            if patient_data["best_m1_prefix"] is None:
                print(f"[{i}/{num_cases}] {patient_id} (scan {scan_id}) — SKIPPED (no M1_ series folder)")
                skipped.append(patient_id)
                continue

            result = download_patient(s3_client, patient_id, patient_data, anomaly_type, i, num_cases)
            results.append(result)

        except Exception as e:
            print(f"[{i}/{num_cases}] {patient_id} (scan {scan_id}) — ERROR: {e}")
            skipped.append(patient_id)

    # --- Phase 4: Summary ---
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
