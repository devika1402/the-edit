# Environment Setup Guide

Full walkthrough for setting up GCP, BigQuery, GCS, and the H&M dataset from scratch.
This guide documents every step, including the pitfalls encountered.

---

## Prerequisites

| Tool | Minimum version | Notes |
|------|----------------|-------|
| macOS (Apple Silicon) | any | Intel Macs: swap `darwin-arm` for `darwin-x86_64` in SDK URL |
| Python 3.13 | 3.13+ | Managed via `fvenv`; Homebrew `python@3.13` recommended |
| Homebrew | any | `brew --version` to check |
| A Google account | n/a | Used to create the GCP project |
| A Kaggle account | n/a | Required to download competition data |

---

## Part 1: Google Cloud SDK

### Why not `brew install --cask google-cloud-sdk`?

The Homebrew cask fails on macOS when Python 3.14 is the default system Python.
The gcloud installer tries to create a virtualenv using Python 3.14, which has a
binary incompatibility with macOS's system `libexpat.1.dylib`:

```
ImportError: dlopen(...pyexpat.cpython-314-darwin.so ...):
  Symbol not found: _XML_SetAllocTrackerActivationThreshold
ERROR: Virtual env setup failed.
```

The cask then rolls back and leaves nothing installed. **Use the standalone installer
instead**, it bundles its own Python and is unaffected by whatever Python is on your
system.

### Install the standalone SDK (Apple Silicon)

```bash
# 1. Download the ARM64 tarball
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-arm.tar.gz

# 2. Extract and run the installer
tar -xf google-cloud-cli-darwin-arm.tar.gz
./google-cloud-sdk/install.sh

# 3. Reload your shell so gcloud and bq are on PATH
source ~/.zshrc

# 4. Verify
gcloud version
```

Expected output includes a line like `Google Cloud SDK 573.0.0`.

---

## Part 2: GCP Project

### Create the project

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Click the project picker (top-left) → **New Project**.
3. Give it a name (e.g. `hm-recsys`). GCP assigns an ID like `your-project-id`, note it.
4. Attach a billing account if prompted (required for GCS; BigQuery sandbox works without one).

This project uses:
- **Project ID:** `your-project-id`
- **BigQuery dataset:** `hm_recommender`
- **Location:** `EU` (the H&M data is European, locked decision D-4)

### Authenticate and enable BigQuery

```bash
# Interactive browser login: sets the active project
gcloud init

# Enable the BigQuery API
gcloud services enable bigquery.googleapis.com

# Write Application Default Credentials: this is what `make auth` runs
gcloud auth application-default login
```

`gcloud auth application-default login` opens a browser tab. After you approve,
it writes credentials to `~/.config/gcloud/application_default_credentials.json`.
The Python BigQuery client picks these up automatically; you never need a
service-account key file for local development.

### Create the BigQuery dataset

```bash
bq --location=EU mk --dataset "$(gcloud config get-value project):hm_recommender"
```

Verify it exists:

```bash
bq ls
```

You should see `hm_recommender` listed.

---

## Part 3: GCS Bucket

The raw CSV files live in a GCS bucket. BigQuery loads from there, which avoids
storing 34 GB of data locally and is the standard pattern for large datasets.

```bash
# Create the bucket in EU (same location as the BigQuery dataset)
gsutil mb -l EU gs://your-project-id-hm-data
```

> **Note:** `gsutil mb` may print a message recommending the newer `gcloud storage`
> CLI. Either tool works; `gsutil` is fine here.

Verify:

```bash
gsutil ls
# Expected: gs://your-project-id-hm-data/
```

---

## Part 4: `.env` File

```bash
cp .env.example .env
```

Then set `GCP_PROJECT` to your project ID. The file should look like:

```dotenv
GCP_PROJECT=your-project-id
BQ_DATASET=hm_recommender
BQ_LOCATION=EU
BQ_MAX_BYTES_BILLED=10000000000

DATA_DIR=data
ARTIFACTS_DIR=artifacts

CUSTOMER_SAMPLE_SIZE=100000
COPURCHASE_WINDOW_DAYS=90
TOP_K=12

LOG_LEVEL=INFO
```

`.env` is git-ignored. Never commit it.

---

## Part 5: Kaggle Data

The H&M files are gated behind Kaggle's competition rules. You must accept them in
your browser before any download will work. Skipping this step causes a silent 403.

### Step 1: Accept the competition rules (browser, one-time)

Go to:
[kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/rules](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/rules)

Scroll to the bottom and click **"I Understand and Accept"**.

### Step 2: Get a Kaggle API token

1. Log in to [kaggle.com](https://kaggle.com).
2. Click your avatar (top-right) → **Settings**.
3. Scroll to the **API** section.
4. Click **"Create New Token"** under **API Tokens** (not the legacy section).
   - This downloads `kaggle.json` containing `{"username": "...", "key": "..."}`.
   - Kaggle CLI >= 1.8.0 also accepts the newer `KGAT_...` token format.

> **Security:** Never paste your token in a chat, terminal history, or commit it.
> If you accidentally expose it, go to Settings → API → **Expire API Token**
> immediately, then create a new one.

### Step 3: Download data via Cloud Shell

We use [GCP Cloud Shell](https://console.cloud.google.com) (the `>_` icon, top-right)
to download the files. Cloud Shell has a fast internal network to GCS and ~200 GB of
ephemeral disk in `/tmp`, no local disk space used on your Mac.

**Open Cloud Shell** and run:

```bash
# Install the Kaggle CLI
pip install kaggle --quiet
export PATH="$HOME/.local/bin:$PATH"

# Place your API token
mkdir -p ~/.kaggle

# Option A: upload kaggle.json via the Cloud Shell upload button (⋮ menu → Upload)
# then:
mv ~/kaggle.json ~/.kaggle/kaggle.json

# Option B: paste contents manually
nano ~/.kaggle/kaggle.json
# Paste: {"username":"YOUR_USERNAME","key":"YOUR_KEY"}  then Ctrl+O, Enter, Ctrl+X

chmod 600 ~/.kaggle/kaggle.json

# Verify auth
kaggle --version       # must be >= 1.8.0
kaggle competitions list   # should return a list, not a 403
```

**Download the three CSV files:**

```bash
# Note: --unzip was removed in kaggle CLI 2.x; unzip manually
for f in transactions_train.csv articles.csv customers.csv; do
  kaggle competitions download \
    -c h-and-m-personalized-fashion-recommendations \
    -f $f -p /tmp
  unzip -o /tmp/${f}.zip -d /tmp
  rm /tmp/${f}.zip
done
```

`transactions_train.csv` is the largest file (~3.5 GB compressed). Expect 5-10 minutes.

**Upload to GCS:**

```bash
gsutil -m cp \
  /tmp/transactions_train.csv \
  /tmp/articles.csv \
  /tmp/customers.csv \
  gs://your-project-id-hm-data/raw/
```

The `-m` flag enables parallel transfers. Verify all three landed:

```bash
gsutil ls gs://your-project-id-hm-data/raw/
```

Expected output:
```
gs://your-project-id-hm-data/raw/articles.csv
gs://your-project-id-hm-data/raw/customers.csv
gs://your-project-id-hm-data/raw/transactions_train.csv
```

---

## Part 6: Python Environment

```bash
make install   # creates fvenv/, installs all deps + dev tools
make auth      # opens browser for ADC (same as gcloud auth application-default login)
```

Verify the environment is healthy:

```bash
make lint       # ruff, should be clean
make typecheck  # mypy strict, should be clean
make test       # pytest, all tests should pass
```

---

## Quick Reference: Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ImportError: dlopen(...pyexpat...)` during brew install | Python 3.14 / libexpat incompatibility | Use the standalone SDK installer (Part 1) |
| `virtualenv: command not found` during brew install | Same brew cask issue | Use the standalone SDK installer |
| `kaggle: error: unrecognized arguments: --unzip` | Removed in kaggle CLI 2.x | Omit `--unzip`; run `unzip` separately (Part 5) |
| `403 Forbidden` on `kaggle competitions download` | Competition rules not accepted | Accept rules at the competition's Rules page (Part 5, Step 1) |
| `gsutil: command not found` | gcloud SDK not on PATH | Run `source ~/.zshrc` or add `google-cloud-sdk/bin` to PATH |
| `BQ access denied` | ADC not set up | Run `gcloud auth application-default login` |
| `.env` not found | File not created | `cp .env.example .env` then fill in `GCP_PROJECT` |

---

## Environment at a Glance

```
GCP Project:    your-project-id
BQ Dataset:     hm_recommender  (location: EU)
GCS Bucket:     gs://your-project-id-hm-data
Raw data path:  gs://your-project-id-hm-data/raw/
Local venv:     fvenv/  (Python 3.13, managed by make install)
Auth method:    Application Default Credentials (ADC) for local dev
```
