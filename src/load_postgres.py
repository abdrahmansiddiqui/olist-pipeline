from __future__ import annotations

import io
import os
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from config import DATE_COLS
from minio_utils import get_minio_client, ensure_bucket, download_object_bytes

load_dotenv()

def wait_for_postgres(timeout_seconds: int = 60) -> None:
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    database = os.getenv("POSTGRES_DB")

    if not all([user, password, host, port, database]):
        raise RuntimeError("Missing Postgres env vars. Check .env (POSTGRES_*).")

    conn_str = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    start = time.time()
    while True:
        try:
            engine = create_engine(conn_str)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as e:
            if time.time() - start > timeout_seconds:
                raise RuntimeError(f"Postgres not ready after {timeout_seconds}s: {e}")
            time.sleep(2)

def get_db_engine():
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    database = os.getenv("POSTGRES_DB")

    connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    return create_engine(connection_string)

def create_schema(engine) -> bool:
    """Create database schema from sql/schema.sql safely (handles BOM + comments)."""
    schema_path = Path("sql/schema.sql")

    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}")
        return False

    # utf-8-sig strips UTF-8 BOM if present
    schema_sql = schema_path.read_text(encoding="utf-8-sig")

    # Remove full-line -- comments (keeps actual SQL)
    cleaned_lines = []
    for line in schema_sql.splitlines():
        if line.lstrip().startswith("--"):
            continue
        cleaned_lines.append(line)

    cleaned_sql = "\n".join(cleaned_lines)

    # Split into individual statements
    statements = [s.strip() for s in cleaned_sql.split(";") if s.strip()]

    print("Creating database schema...")

    # engine.begin() auto-commits, auto-rollbacks on error
    with engine.begin() as conn:
        for stmt in statements:
            # exec_driver_sql is best for raw SQL/DDL
            conn.exec_driver_sql(stmt)

    print("✓ Schema created successfully")
    return True

def _read_processed_csv_bytes(dataset_name: str, data: bytes) -> pd.DataFrame:
    # parse dates explicitly for stable insertion
    parse_dates = DATE_COLS.get(dataset_name, [])
    return pd.read_csv(io.BytesIO(data), parse_dates=parse_dates)

def load_from_minio_processed(processed_bucket: str, engine):
    client = get_minio_client()
    ensure_bucket(client, processed_bucket)

    # FK-safe load order
    load_order = [
        ("customers", "customers_clean.csv"),
        ("sellers", "sellers_clean.csv"),
        ("product_category_name_translation", "product_category_name_translation_clean.csv"),
        ("products", "products_clean.csv"),
        ("orders", "orders_clean.csv"),
        ("order_items", "order_items_clean.csv"),
        ("order_payments", "order_payments_clean.csv"),
        ("order_reviews", "order_reviews_clean.csv"),
        ("geolocation", "geolocation_clean.csv"),
    ]

    print("\n" + "=" * 70)
    print("LOADING DATA INTO POSTGRES (from MinIO processed)")
    print("=" * 70)

    for table_name, object_name in load_order:
        print(f"\nLoading {table_name} from MinIO object: {object_name}")

        data = download_object_bytes(client, processed_bucket, object_name)
        df = _read_processed_csv_bytes(table_name, data)

        df.to_sql(
            table_name,
            engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=5000,
        )

        print(f"  ✓ Loaded {len(df):,} rows into {table_name}")

    print("\n✓ All data loaded successfully!")

def verify_data(engine):
    print("\n" + "=" * 70)
    print("VERIFYING DATA")
    print("=" * 70)

    queries = {
        "Total Customers": "SELECT COUNT(*) AS count FROM customers",
        "Total Orders": "SELECT COUNT(*) AS count FROM orders",
        "Total Order Items": "SELECT COUNT(*) AS count FROM order_items",
        "Total Products": "SELECT COUNT(*) AS count FROM products",
        "Total Sellers": "SELECT COUNT(*) AS count FROM sellers",
        "Order Status Distribution": """
            SELECT order_status, COUNT(*) AS count
            FROM orders
            GROUP BY order_status
            ORDER BY count DESC
        """,
    }

    for name, query in queries.items():
        print(f"\n{name}:")
        result = pd.read_sql(query, engine)
        print(result.to_string(index=False))

if __name__ == "__main__":
    wait_for_postgres(90)
    engine = get_db_engine()
    create_schema(engine)

    processed_bucket = os.getenv("MINIO_BUCKET_PROCESSED", "olist-processed")
    load_from_minio_processed(processed_bucket, engine)

    verify_data(engine)
