import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

def get_db_engine():
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB")

    if not all([user, password, database]):
        raise RuntimeError("Missing Postgres env vars. Check .env (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB).")

    conn_str = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    return create_engine(conn_str)

def create_schema(engine) -> bool:
    schema_path = Path("sql/schema.sql")
    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}")
        return False

    # utf-8-sig removes BOM if PowerShell wrote one
    schema_sql = schema_path.read_text(encoding="utf-8-sig")

    # drop full-line '--' comments (safe for statement splitting)
    cleaned_lines = []
    for line in schema_sql.splitlines():
        if line.lstrip().startswith("--"):
            continue
        cleaned_lines.append(line)
    cleaned_sql = "\n".join(cleaned_lines)

    statements = [s.strip() for s in cleaned_sql.split(";") if s.strip()]

    print("Creating database schema...")
    with engine.begin() as conn:
        for stmt in statements:
            conn.exec_driver_sql(stmt)
    print("✓ Schema created successfully")
    return True

def load_data_to_postgres(processed_dir: str, engine):
    processed_dir = Path(processed_dir)

    # Order matters because of foreign keys
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
    print("LOADING DATA INTO POSTGRES (from local processed_dir)")
    print("=" * 70)

    for table_name, filename in load_order:
        csv_path = processed_dir / filename

        if not csv_path.exists():
            print(f"⚠ Skipping {table_name}: missing file {csv_path}")
            continue

        print(f"\nLoading {table_name} from {csv_path} ...")

        df = pd.read_csv(csv_path)

        df.to_sql(
            table_name,
            engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=2000,
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

    for name, q in queries.items():
        print(f"\n{name}:")
        res = pd.read_sql(q, engine)
        print(res.to_string(index=False))
