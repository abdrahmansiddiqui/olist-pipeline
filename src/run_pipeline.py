import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# ---------------------------
# Redirect EVERYTHING to log only (FD 1/2 + sys stdout/stderr)
# ---------------------------
def redirect_everything_to_log_only():
    log_path = Path(__file__).resolve().parent / "logs" / "run_pipeline_log.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log_file = open(log_path, "a", encoding="utf-8", errors="replace", newline="\n")
    log_file.write(
        "\n\n" + "=" * 110 +
        f"\nRUN START: {datetime.now().isoformat(timespec='seconds')}" +
        f"\nLOG FILE: {log_path}" +
        "\n" + "=" * 110 + "\n"
    )
    log_file.flush()

    os.dup2(log_file.fileno(), 1)  # stdout
    os.dup2(log_file.fileno(), 2)  # stderr

    sys.stdout = open(1, "w", encoding="utf-8", errors="replace", closefd=False)
    sys.stderr = open(2, "w", encoding="utf-8", errors="replace", closefd=False)

    return log_file, log_path

_LOG_FILE, _LOG_PATH = redirect_everything_to_log_only()

# ---------------------------
# Bootstrap helpers
# ---------------------------
EXPECTED_RAW_FILES = [
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]

SCHEMA_SQL = """
-- Drop existing tables (child -> parent)
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS order_payments CASCADE;
DROP TABLE IF EXISTS order_reviews CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS product_category_name_translation CASCADE;
DROP TABLE IF EXISTS sellers CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS geolocation CASCADE;

-- Customers
CREATE TABLE customers (
    customer_id VARCHAR(255) PRIMARY KEY,
    customer_unique_id VARCHAR(255) NOT NULL,
    customer_zip_code_prefix VARCHAR(10),
    customer_city VARCHAR(255),
    customer_state VARCHAR(2)
);

-- Sellers
CREATE TABLE sellers (
    seller_id VARCHAR(255) PRIMARY KEY,
    seller_zip_code_prefix VARCHAR(10),
    seller_city VARCHAR(255),
    seller_state VARCHAR(2)
);

-- Category translation
CREATE TABLE product_category_name_translation (
    product_category_name VARCHAR(255) PRIMARY KEY,
    product_category_name_english VARCHAR(255)
);

-- Products
CREATE TABLE products (
    product_id VARCHAR(255) PRIMARY KEY,
    product_category_name VARCHAR(255),
    product_name_length INTEGER,
    product_description_length INTEGER,
    product_photos_qty INTEGER,
    product_weight_g INTEGER,
    product_length_cm INTEGER,
    product_height_cm INTEGER,
    product_width_cm INTEGER,
    CONSTRAINT fk_products_category
      FOREIGN KEY (product_category_name)
      REFERENCES product_category_name_translation(product_category_name)
);

-- Orders
CREATE TABLE orders (
    order_id VARCHAR(255) PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    order_status VARCHAR(50),
    order_purchase_timestamp TIMESTAMP,
    order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP,
    CONSTRAINT fk_orders_customer
      FOREIGN KEY (customer_id)
      REFERENCES customers(customer_id)
);

-- Order Items
CREATE TABLE order_items (
    order_id VARCHAR(255) NOT NULL,
    order_item_id INTEGER NOT NULL,
    product_id VARCHAR(255) NOT NULL,
    seller_id VARCHAR(255) NOT NULL,
    shipping_limit_date TIMESTAMP,
    price DECIMAL(10, 2),
    freight_value DECIMAL(10, 2),
    PRIMARY KEY (order_id, order_item_id),
    CONSTRAINT fk_items_order
      FOREIGN KEY (order_id) REFERENCES orders(order_id),
    CONSTRAINT fk_items_product
      FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT fk_items_seller
      FOREIGN KEY (seller_id) REFERENCES sellers(seller_id)
);

-- Payments
CREATE TABLE order_payments (
    order_id VARCHAR(255) NOT NULL,
    payment_sequential INTEGER NOT NULL,
    payment_type VARCHAR(50),
    payment_installments INTEGER,
    payment_value DECIMAL(10, 2),
    PRIMARY KEY (order_id, payment_sequential),
    CONSTRAINT fk_payments_order
      FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- Reviews
CREATE TABLE order_reviews (
    review_id VARCHAR(255) PRIMARY KEY,
    order_id VARCHAR(255) NOT NULL,
    review_score INTEGER CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TIMESTAMP,
    review_answer_timestamp TIMESTAMP,
    CONSTRAINT fk_reviews_order
      FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- Geolocation (no PK)
-- IMPORTANT: use DOUBLE PRECISION to avoid numeric overflow issues.
CREATE TABLE geolocation (
    geolocation_zip_code_prefix VARCHAR(10),
    geolocation_lat DOUBLE PRECISION,
    geolocation_lng DOUBLE PRECISION,
    geolocation_city VARCHAR(255),
    geolocation_state VARCHAR(2)
);

-- Indexes
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(order_status);
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_order_items_seller ON order_items(seller_id);
CREATE INDEX idx_geolocation_zip ON geolocation(geolocation_zip_code_prefix);
"""


def ensure_dirs():
    for p in [
        Path("data/raw"),
        Path("data/processed"),
        Path("data/rejected"),
        Path("sql"),
        Path("src/logs"),
    ]:
        p.mkdir(parents=True, exist_ok=True)
    print("✓ Ensured folder structure exists")


def ensure_env():
    env = Path(".env")
    env_example = Path(".env.example")

    if not env_example.exists():
        print("⚠ .env.example missing - create it in repo root (recommended).")

    if not env.exists():
        if env_example.exists():
            env.write_text(env_example.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
            print("✓ Created .env from .env.example")
        else:
            # fallback minimal env
            env.write_text(
                """
# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET_RAW=olist-raw
MINIO_BUCKET_PROCESSED=olist-processed

# Postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=olistdb
POSTGRES_USER=olist
POSTGRES_PASSWORD=olistpw
""",
                encoding="utf-8",
                newline="\\n",
            )
            print("✓ Created .env with default local dev values")
    else:
        print("✓ .env already exists")


def ensure_schema_file():
    schema_path = Path("sql/schema.sql")
    if not schema_path.exists():
        schema_path.write_text(SCHEMA_SQL, encoding="utf-8", newline="\n")
        print("✓ Created sql/schema.sql")
    else:
        # Also remove BOM if present (prevents the comment-line syntax error)
        txt = schema_path.read_text(encoding="utf-8-sig")
        schema_path.write_text(txt, encoding="utf-8", newline="\n")
        print("✓ sql/schema.sql exists (normalized encoding to UTF-8 no BOM)")


def try_start_docker():
    compose = Path("docker-compose.yml")
    if not compose.exists():
        print("⚠ docker-compose.yml not found. Docker services will not be auto-started.")
        return

    if shutil.which("docker") is None:
        print("⚠ docker command not found. Install Docker Desktop, then rerun.")
        return

    try:
        subprocess.run(["docker", "compose", "up", "-d"], check=True, capture_output=True, text=True)
        print("✓ docker compose up -d ran successfully")
    except subprocess.CalledProcessError as e:
        print("⚠ docker compose up -d failed.")
        print(e.stdout)
        print(e.stderr)


def raw_files_present() -> bool:
    raw_dir = Path("data/raw")
    existing = {p.name for p in raw_dir.glob("*.csv")}
    missing = [f for f in EXPECTED_RAW_FILES if f not in existing]
    if missing:
        print("⚠ Missing raw CSV files in data/raw:")
        for f in missing:
            print(f"  - {f}")
        return False
    print("✓ Raw CSVs present in data/raw")
    return True


def try_kaggle_download_if_possible() -> bool:
    # Only attempt if kaggle CLI exists and kaggle.json exists
    if shutil.which("kaggle") is None:
        print("⚠ Kaggle CLI not found; cannot auto-download.")
        return False

    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if not kaggle_json.exists():
        print("⚠ Kaggle config not found at ~/.kaggle/kaggle.json; cannot auto-download.")
        return False

    try:
        print("Attempting Kaggle download -> data/raw ...")
        subprocess.run(
            ["kaggle", "datasets", "download", "-d", "olistbr/brazilian-ecommerce", "-p", "data/raw", "--unzip"],
            check=True,
            text=True,
        )
        print("✓ Kaggle download complete")
        return True
    except subprocess.CalledProcessError as e:
        print("⚠ Kaggle download failed.")
        print(str(e))
        return False


def bootstrap():
    print("=" * 80)
    print("BOOTSTRAP: initialize folders/files/services")
    print("=" * 80)

    ensure_dirs()
    ensure_env()
    ensure_schema_file()
    try_start_docker()

    if raw_files_present():
        return

    # Try kaggle download; if still missing, exit with instructions
    ok = try_kaggle_download_if_possible()
    if ok and raw_files_present():
        return

    print("\\n❌ Raw data not available.")
    print("Fix one of these:")
    print("  A) Manual: Download the Olist dataset zip from Kaggle and extract CSVs into data/raw/")
    print("  B) Kaggle API: Put kaggle.json at ~/.kaggle/kaggle.json and ensure kaggle CLI works.")
    raise SystemExit(2)


# ---------------------------
# Your existing pipeline imports and runner
# ---------------------------
from upload_minio_raw import upload_raw_csvs
from etl_clean import process_from_minio
from load_postgres import get_db_engine, create_schema, load_data_to_postgres, verify_data
from dotenv import load_dotenv

def run_full_pipeline():
    load_dotenv()

    print("=" * 80)
    print(" OLIST E-COMMERCE DATA PIPELINE (Kaggle/local -> MinIO raw -> ETL -> MinIO processed -> Postgres)")
    print("=" * 80)

    # [INIT] Bootstrap project state first
    bootstrap()

    # [0] Wait for services etc (keep your existing logic if you have it)
    # If you already have wait_for_services(), call it here.

    print("\n[1/4] Uploading raw CSVs from data/raw -> MinIO raw bucket...")
    upload_raw_csvs()

    print("\n[2/4] Transform: MinIO raw -> cleaned -> MinIO processed + data/processed ...")
    raw_bucket = os.getenv("MINIO_BUCKET_RAW", "olist-raw")
    processed_bucket = os.getenv("MINIO_BUCKET_PROCESSED", "olist-processed")
    process_from_minio(raw_bucket, processed_bucket, "data/processed")

    print("\n[3/4] Creating Postgres schema...")
    engine = get_db_engine()
    ok = create_schema(engine)
    if not ok:
        raise RuntimeError("Schema creation failed. Ensure sql/schema.sql exists and is valid.")

    print("\n[4/4] Load: MinIO processed -> Postgres ...")
    load_data_to_postgres("data/processed", engine)

    print("\n" + "=" * 80)
    print("PIPELINE DONE ✅")
    print("=" * 80)
    verify_data(engine)


if __name__ == "__main__":
    try:
        run_full_pipeline()
    finally:
        try:
            _LOG_FILE.flush()
        finally:
            _LOG_FILE.close()
