# Olist Data Pipeline (Kaggle -> MinIO -> ETL -> Postgres)

This project builds a complete local data pipeline using the Brazilian Olist e-commerce dataset:
- Raw CSVs stored in **MinIO** (S3-compatible object storage)
- Cleaned/validated CSVs stored in **MinIO processed bucket** + local `data/processed`
- Final tables loaded into **Postgres**
- You can browse the DB using **pgAdmin**

✅ The pipeline includes an **initialization/bootstrap step** inside `src/run_pipeline.py`:
- creates required folders
- ensures `.env` exists (creates it from `.env.example` if missing)
- ensures `sql/schema.sql` exists (creates a correct schema if missing)
- starts Docker services (if Docker is installed)
- checks for raw CSVs and tries to auto-download via Kaggle CLI (if configured)

---

## What You Need Installed

### Required
1) **Python 3.11+**
2) **Docker Desktop** (to run Postgres + pgAdmin + MinIO containers)

### Optional (for auto-download)
- **Kaggle CLI** + `kaggle.json` configured  
If you don’t have this, you can manually download the dataset zip and place CSVs in `data/raw`.

---

## Quick Start (Recommended)

### 1) Clone the repo
```bash
git clone <YOUR_REPO_URL>
cd olist-pipeline
```

### 2) Start Docker Desktop
Make sure Docker Desktop is running.

### 3) Create Python environment + install dependencies

```bash
uv venv --python 3.11
# Windows PowerShell:
.venv\Scripts\Activate.ps1
uv sync
```

### 4) Run the pipeline (this also initializes everything)
```bash
python src/run_pipeline.py
```

⚠️ **Important:** This project redirects all output to a log file (not the console).  
After running, open the log:

```bash
notepad src/logs/run_pipeline_log.txt
```

---

## Getting the Dataset (Raw CSVs)

The pipeline needs these CSVs inside `data/raw/`:
- `olist_customers_dataset.csv`
- `olist_geolocation_dataset.csv`
- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`
- `product_category_name_translation.csv`

### Option A (Easiest): Manual download
1) Go to the Kaggle dataset page: **Olist Brazilian E-Commerce**
2) Download the zip
3) Extract it
4) Copy all `.csv` files into `data/raw/`

Then rerun:
```bash
python src/run_pipeline.py
```

### Option B: Kaggle CLI auto-download (optional)
1) Go to Kaggle settings → API → “Create New Token”
2) Put the downloaded `kaggle.json` here:
   - Windows: `C:\Users\<you>\.kaggle\kaggle.json`
3) Install Kaggle CLI (in your venv):
```bash
pip install kaggle
```

Then rerun:
```bash
python src/run_pipeline.py
```

The bootstrap step will auto-download into `data/raw/`.

---

## Services + Web UIs

When Docker is running, these are available:

### MinIO
- Console: http://localhost:9001
- User: `minioadmin`
- Pass: `minioadmin123`

Buckets used:
- Raw: `olist-raw`
- Processed: `olist-processed`

### Postgres
- Host (from your machine): `localhost`
- Port: `5432`
- DB: `olistdb`
- User: `olist`
- Pass: `olistpw`

### pgAdmin
- URL: http://localhost:5050
- Email: `admin@admin.com`
- Password: `admin`

---

## How to Connect pgAdmin to Postgres

Inside pgAdmin:
1) Right-click **Servers** → Register → Server
2) General tab: Name = `Olist DB`
3) Connection tab:
   - Host name/address: `postgres`  ✅ (IMPORTANT: not localhost)
   - Port: `5432`
   - Maintenance DB: `olistdb`
   - Username: `olist`
   - Password: `olistpw`
   - Save password ✅
4) Save

---

## Useful SQL Checks

```sql
SELECT COUNT(*) FROM customers;
SELECT COUNT(*) FROM orders;
SELECT COUNT(*) FROM order_items;

SELECT order_status, COUNT(*)
FROM orders
GROUP BY order_status
ORDER BY COUNT(*) DESC;

SELECT *
FROM order_reviews
WHERE review_id = 'PUT_REVIEW_ID_HERE';
```

---

## Output Folders

- `data/raw/`  
  Raw CSVs (not committed to GitHub)

- `data/processed/`  
  Cleaned CSVs (not committed)

- `data/rejected/`  
  Rows quarantined for analysis (duplicates, etc.) (not committed)

- `src/logs/run_pipeline_log.txt`  
  Pipeline log output (not committed)

---

## Troubleshooting

### “docker is not recognized”
Install Docker Desktop and ensure it’s running, then rerun.

### “Raw data not available”
You didn’t put CSVs in `data/raw/` and Kaggle download isn’t configured.
Use Option A (manual download) or configure Kaggle CLI.

### Schema errors
The schema is auto-created as `sql/schema.sql` if missing.  
If you edited it manually and broke it, delete `sql/schema.sql` and rerun the pipeline to regenerate.

---

## Notes on Data Cleaning
- Invalid product category names are mapped to an `"unknown"` category instead of dropping rows.
- Duplicate reviews are deduplicated by `review_id` and saved to `data/rejected/` for later inspection.
