# S3 CT Brain Scan DataLoader

A Python script that connects to AWS S3, randomly selects **600 patient CT brain scan cases** from the hospital database, and downloads their DICOM files along with associated reports (XML and DOC) to a local folder.

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

The script needs `boto3` (AWS SDK) and `python-dotenv` (loads credentials from a `.env` file). Install both:

```
pip install boto3 python-dotenv
```

To verify they installed correctly:
```
pip show boto3 python-dotenv
```
You should see package information for both.

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
```

> **⚠️ SECURITY:** The `.env` file is git-ignored and will NOT be pushed to GitHub.  
> **Never** put credentials directly in `DataLoader.py` or any other tracked file.  
> If you accidentally commit credentials, rotate them immediately in the AWS console.

If the `.env` file is missing or incomplete, the script will print an error and exit.

### 2. Number of patients (OPTIONAL)

By default the script selects **600** random patients. To change this, edit this line in `DataLoader.py`:

```python
NUM_PATIENTS = 600
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

### Step 2: Run the script

```
python DataLoader.py
```

### What to expect

1. The script will connect to S3 and list all patient folders — this may take a minute.
2. It will randomly select 600 patients (or fewer if less are available).
3. For each patient, it will:
   - Find the CT scan series with the most DICOM files
   - Download those DICOM files
   - Download any XML reports
   - Download any DOC reports
4. Progress is printed for each patient:
   ```
   [1/600] P00000222267990 — 45 DICOMs, 1 XML, 1 DOC
   [2/600] P00000333378001 — 32 DICOMs, 1 XML, 0 DOC
   ...
   ```
5. At the end, a summary is printed with totals.
6. A `manifest.csv` file is saved in the output directory with details of all downloaded patients.

### Estimated runtime

Depending on your internet speed and the size of the DICOM files, downloading 600 patients may take **several hours**. The script prints progress so you can monitor it.

---

## Output Structure

After the script completes, the output directory will look like this:

```
downloaded_data/
├── manifest.csv                          ← CSV with all patient details
├── P00000222267990/
│   ├── dicoms/
│   │   ├── slice_001.dcm
│   │   ├── slice_002.dcm
│   │   └── ...
│   └── reports/
│       ├── report.xml
│       └── report.doc
├── P00000333378001/
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

### "ModuleNotFoundError: No module named 'boto3'"
You haven't installed boto3. Run:
```
pip install boto3
```
Make sure your virtual environment is activated first.

### "botocore.exceptions.ClientError: An error occurred (AccessDenied)"
Your AWS credentials don't have permission to access the S3 bucket. Check with your project administrator that your IAM user has `s3:ListBucket` and `s3:GetObject` permissions on the `bioanalytixdata` bucket.

### "botocore.exceptions.NoCredentialsError"
You haven't filled in the AWS credentials in `DataLoader.py`. See the [Configuration](#configuration) section.

### "botocore.exceptions.EndpointConnectionError"
Check your internet connection, or verify that the `AWS_REGION` value is correct.

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
