# S3 CT Brain Scan DataLoader

Two Python scripts that work together to select **600 random CT brain scan cases** from a PostgreSQL database and download their DICOM files and reports from AWS S3.

| Script | Purpose |
|---|---|
| `QueryDB.py` | Queries the database, selects 600 random cases with anomalies, outputs `selected_cases.csv` |
| `DataLoader.py` | Reads the CSV, downloads matching DICOM files + reports from S3 |

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [How to Run](#how-to-run)
5. [Output Structure](#output-structure)
6. [S3 Database Structure](#s3-database-structure)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before running the script, make sure you have the following installed on your machine:

### 1. Python 3.10 or higher

- **Download:** Go to [https://www.python.org/downloads/](https://www.python.org/downloads/) and download the latest Python installer for Windows.
- **Install:** Run the installer. **IMPORTANT:** Check the box that says **"Add Python to PATH"** at the bottom of the first screen before clicking "Install Now".
- **Verify:** Open a Command Prompt or PowerShell and run:
  ```
  python --version
  ```
  You should see something like `Python 3.13.0`.

### 2. pip (Python package manager)

pip comes bundled with Python. Verify it is available:
```
pip --version
```
If it's not found, run:
```
python -m ensurepip --upgrade
```

### 3. AWS Credentials

You need valid AWS credentials (Access Key ID and Secret Access Key) with **read access** to the S3 bucket `bioanalytixdata`. Ask your project administrator if you don't have these.

### 4. PostgreSQL Database Access

You need access to the PostgreSQL database that contains the `ct_scans` and `anomalies` tables. You'll need: host, port, database name, username, and password.

---

## Installation

### Step 1: Clone the repository

Open a terminal (PowerShell or Command Prompt) and run:

```
git clone https://github.com/ChristosLeptokaropoulos/Labels_python_script.git
```

Then navigate into the project folder:

```
cd Labels_python_script
```

### Step 2: (Recommended) Create a virtual environment

This isolates the project's dependencies from your system Python:

```
python -m venv .venv
```

Activate the virtual environment:

- **PowerShell:**
  ```
  .\.venv\Scripts\Activate.ps1
  ```
- **Command Prompt:**
  ```
  .\.venv\Scripts\activate.bat
  ```

You should see `(.venv)` at the beginning of your terminal prompt.

### Step 3: Install required packages

The scripts need `boto3` (AWS SDK), `python-dotenv` (loads credentials from `.env`), and `psycopg2-binary` (PostgreSQL driver). Install all:

```
pip install boto3 python-dotenv psycopg2-binary
```

To verify they installed correctly:
```
pip show boto3 python-dotenv psycopg2-binary
```
You should see package information for all three.

---

## Configuration

### 1. AWS Credentials (REQUIRED) — via `.env` file

Credentials are loaded from a **`.env` file** that stays on your machine and is **never pushed to GitHub** (it is listed in `.gitignore`).

**Step 1:** Copy the example template to create your own `.env` file:

```
copy .env.example .env
```

**Step 2:** Open the new `.env` file in any text editor and fill in your real values:

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=wJalr...
AWS_REGION=eu-west-1

DB_HOST=your_database_host
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_username
DB_PASSWORD=your_password
```

> **⚠️ SECURITY:** The `.env` file is git-ignored and will NOT be pushed to GitHub.  
> **Never** put credentials directly in any `.py` file or any other tracked file.  
> If you accidentally commit credentials, rotate them immediately.

If the `.env` file is missing or incomplete, both scripts will print an error and exit.

### 2. Number of cases (OPTIONAL)

By default `QueryDB.py` selects **600** random cases. To change this, edit this line in `QueryDB.py`:

```python
NUM_CASES = 600
```

### 3. Output directory (OPTIONAL)

By default, files are downloaded to `C:\Users\user\Desktop\Labels_orasis\downloaded_data`. To change this, edit this line in `DataLoader.py`:

```python
LOCAL_OUTPUT_DIR = r"C:\Users\user\Desktop\Labels_orasis\downloaded_data"
```

---

## How to Run

### Step 1: Make sure your virtual environment is activated

If you see `(.venv)` in your terminal prompt, you're good. If not, activate it:

```
.\.venv\Scripts\Activate.ps1
```

### Step 2: Run QueryDB.py (select cases from database)

```
python QueryDB.py
```

This will:
1. Connect to the PostgreSQL database
2. Select 600 random CT scans that have a **non-NULL anomaly_type**
3. Save the results to `selected_cases.csv` in the script folder
4. Print a summary with the anomaly type distribution

Example output:
```
Selecting 600 random scans with non-NULL anomaly_type...
Retrieved 600 cases.

SUMMARY
Total cases selected: 600
Anomaly type distribution:
  hemorrhage: 142
  fracture: 98
  ...
```

### Step 3: Run DataLoader.py (download from S3)

```
python DataLoader.py
```

This will:
1. Read `selected_cases.csv`
2. For each case, find the CT scan series with the most DICOM files on S3
3. Download those DICOM files + XML and DOC reports
4. Print progress per patient:
   ```
   [1/600] P109259 — 45 DICOMs, 1 XML, 1 DOC
   [2/600] P203841 — 32 DICOMs, 1 XML, 0 DOC
   ...
   ```
5. Save a `manifest.csv` in the output directory with download details

### Estimated runtime

- **QueryDB.py**: A few seconds
- **DataLoader.py**: Several hours depending on internet speed and DICOM file sizes. The script prints progress so you can monitor it.

---

## Output Structure

After running both scripts, you will have:

### `selected_cases.csv` (in the script folder)

Produced by `QueryDB.py`. Contains the 600 selected cases with columns:
- `scan_id` — Database scan ID
- `patient_id` — Patient identifier
- `s3_path` — Full S3 path to the R1_ report folder
- `anomaly_type` — Type of anomaly for this scan

### Downloaded data (in the output folder)

Produced by `DataLoader.py`:

```
downloaded_data/
├── manifest.csv                          ← CSV with download details
├── P109259/
│   ├── dicoms/
│   │   ├── slice_001.dcm
│   │   ├── slice_002.dcm
│   │   └── ...
│   └── reports/
│       ├── report.xml
│       └── report.doc
├── P203841/
│   ├── dicoms/
│   │   └── ...
│   └── reports/
│       └── ...
└── ...
```

- **`dicoms/`** — Contains all DICOM files from the CT scan series with the most slices.
- **`reports/`** — Contains the XML report and/or the DOC report (if they exist).
- **`manifest.csv`** — A spreadsheet-compatible file with columns:
  - `patient_id` — The patient folder name
  - `anomaly_type` — Type of anomaly for this scan
  - `dicom_count` — Number of DICOM files downloaded
  - `xml_count` — Number of XML reports downloaded
  - `doc_count` — Number of DOC reports downloaded
  - `has_report` — Whether any report was found (True/False)
  - `s3_study_path` — The full S3 path to the study folder
  - `s3_series_path` — The full S3 path to the selected DICOM series folder

---

## S3 Database Structure

The script expects the following directory structure on S3:

```
s3://bioanalytixdata/Orasis_Project/CT_Brain_Scans/G.H.Larissa/Dicom_Files/Old_PACS/
└── P{numbers}/                          ← Patient folder (e.g. P00000222267990)
    └── S1_{numbers}/                    ← Study folder (one per patient)
        ├── M1_{numbers}/                ← Series folder (contains DICOM .dcm files)
        ├── M1_{numbers}/                ← Another series (script picks the largest)
        ├── M1_{numbers}/                ← ...
        ├── report.xml                   ← XML report file
        └── R1_{numbers}/                ← Report folder
            └── report.doc               ← DOC report file
```

- **P + numbers** = Patient folder
- **S1_ + numbers** = Study folder (one per patient)
- **M1_ + numbers** = Series folders (multiple per study, contain DICOM slices)
- **R1_ + numbers** = Report folder (may contain .doc or .docx file)

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'boto3'" or 'psycopg2' or 'dotenv'
You haven't installed the required packages. Run:
```
pip install boto3 python-dotenv psycopg2-binary
```
Make sure your virtual environment is activated first.

### "ERROR: Database credentials not found."
You haven't added the DB credentials to your `.env` file. See the [Configuration](#configuration) section.

### "psycopg2.OperationalError: could not connect to server"
Check that: (1) the DB_HOST and DB_PORT are correct, (2) the database server is running, (3) your machine can reach the server (VPN, firewall, etc.).

### "ERROR: Query returned no results"
The `ct_scans` and `anomalies` tables may be empty, or all `anomaly_type` values are NULL. Check the database directly.

### "ERROR: Input CSV not found: selected_cases.csv"
You need to run `QueryDB.py` first before running `DataLoader.py`.

### "botocore.exceptions.ClientError: An error occurred (AccessDenied)"
Your AWS credentials don't have permission to access the S3 bucket. Check with your project administrator that your IAM user has `s3:ListBucket` and `s3:GetObject` permissions on the `bioanalytixdata` bucket.

### "botocore.exceptions.NoCredentialsError"
You haven't filled in the AWS credentials in your `.env` file. See the [Configuration](#configuration) section.

### "botocore.exceptions.EndpointConnectionError"
Check your internet connection, or verify that the `AWS_REGION` value in `.env` is correct.

### "ERROR: No patient folders found"
The S3 path may be incorrect, or the credentials may be wrong. Double-check the bucket name and prefix in the script.

### The script is very slow
This is expected — it needs to make many S3 API calls (listing folders, counting files) and then download potentially thousands of DICOM files. Let it run in the background.

### "ExecutionPolicy" error when activating .venv in PowerShell
Run this command first to allow scripts:
```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then try activating the virtual environment again.
