"""
QueryDB.py
Connects to the PostgreSQL database, joins ct_scans with anomalies,
selects 600 random scans that have a non-NULL anomaly_type,
and writes the results to selected_cases.csv.
"""

import os
import sys
import csv
from collections import Counter

import psycopg2
from dotenv import load_dotenv

# ============================================================
# DB CREDENTIALS — Loaded from .env file (never commit .env)
# ============================================================
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

if not all([DB_HOST, DB_NAME, DB_USER, DB_PASSWORD]):
    print("ERROR: Database credentials not found.")
    print("Add these to your .env file:")
    print("  DB_HOST=your_host")
    print("  DB_PORT=5432")
    print("  DB_NAME=your_database_name")
    print("  DB_USER=your_username")
    print("  DB_PASSWORD=your_password")
    print("See .env.example for a template.")
    sys.exit(1)

# ============================================================
# CONFIGURATION
# ============================================================
NUM_CASES = 600
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "selected_cases.csv")

QUERY = """
    SELECT
        cs.scan_id,
        cs.patient_id,
        cs.s3_path,
        a.anomaly_type
    FROM ct_scans cs
    INNER JOIN anomalies a ON a.scan_id = cs.scan_id
    WHERE a.anomaly_type IS NOT NULL
    ORDER BY RANDOM()
    LIMIT %s;
"""


def main():
    print("=" * 60)
    print("QueryDB — Select Random Cases from Database")
    print("=" * 60)

    # --- Connect to PostgreSQL ---
    print(f"\nConnecting to database '{DB_NAME}' at {DB_HOST}:{DB_PORT}...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
    except psycopg2.Error as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    print("Connected.\n")

    # --- Execute query ---
    print(f"Selecting {NUM_CASES} random scans with non-NULL anomaly_type...")
    try:
        with conn.cursor() as cur:
            cur.execute(QUERY, (NUM_CASES,))
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
    except psycopg2.Error as e:
        print(f"ERROR: Query failed: {e}")
        conn.close()
        sys.exit(1)

    conn.close()

    if not rows:
        print("ERROR: Query returned no results. Check table names and data.")
        sys.exit(1)

    print(f"Retrieved {len(rows)} cases.\n")

    # --- Write CSV ---
    print(f"Writing to: {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(colnames)
        writer.writerows(rows)

    # --- Summary ---
    anomaly_types = [row[3] for row in rows]
    type_counts = Counter(anomaly_types)

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total cases selected: {len(rows)}")
    print(f"Output file:          {OUTPUT_CSV}")
    print(f"\nAnomaly type distribution:")
    for atype, count in type_counts.most_common():
        print(f"  {atype}: {count}")

    print("\nDone. Now run DataLoader.py to download the data from S3.")


if __name__ == "__main__":
    main()
