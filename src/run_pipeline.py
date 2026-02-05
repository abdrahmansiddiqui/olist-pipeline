from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv

from minio_utils import wait_for_minio, get_minio_client, ensure_bucket
from upload_minio_raw import upload_raw_csvs
from etl_clean import process_from_minio
from load_postgres import wait_for_postgres, get_db_engine, create_schema, load_from_minio_processed, verify_data

def redirect_everything_to_log_only():
    """
    Redirect OS-level stdout/stderr (FD 1/2) + Python sys.stdout/sys.stderr
    to a log file ONLY (no console output).
    """
    log_path = Path(__file__).resolve().parent / "logs" / "run_pipeline_log.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Open log file (append). Use utf-8 with replace to avoid crashes on weird characters.
    log_file = open(log_path, "a", encoding="utf-8", errors="replace", newline="\n")

    log_file.write(
        "\n\n" + "=" * 110 +
        f"\nRUN START: {datetime.now().isoformat(timespec='seconds')}" +
        f"\nLOG FILE: {log_path}" +
        "\n" + "=" * 110 + "\n"
    )
    log_file.flush()

    # Redirect OS-level stdout/stderr to the log file
    os.dup2(log_file.fileno(), 1)  # stdout
    os.dup2(log_file.fileno(), 2)  # stderr

    # Now ensure Python-level stdout/stderr also point to those fds (text mode)
    sys.stdout = open(1, "w", encoding="utf-8", errors="replace", closefd=False)
    sys.stderr = open(2, "w", encoding="utf-8", errors="replace", closefd=False)

    return log_file, log_path

# IMPORTANT: call it immediately so even early prints go to file
_LOG_FILE, _LOG_PATH = redirect_everything_to_log_only()

load_dotenv()



def run_full_pipeline():
    print("=" * 80)
    print(" OLIST E-COMMERCE DATA PIPELINE (Kaggle/local -> MinIO raw -> ETL -> MinIO processed -> Postgres)")
    print("=" * 80)

    raw_bucket = os.getenv("MINIO_BUCKET_RAW", "olist-raw")
    processed_bucket = os.getenv("MINIO_BUCKET_PROCESSED", "olist-processed")

    print("\n[0] Waiting for MinIO + Postgres to be ready...")
    wait_for_minio(90)
    wait_for_postgres(90)
    print("✓ Services ready")

    # Ensure buckets exist
    client = get_minio_client()
    ensure_bucket(client, raw_bucket)
    ensure_bucket(client, processed_bucket)

    print("\n[1/4] Uploading raw CSVs from data/raw -> MinIO raw bucket...")
    upload_raw_csvs()

    print("\n[2/4] Transform: MinIO raw -> cleaned -> MinIO processed + data/processed ...")
    process_from_minio(raw_bucket, processed_bucket, "data/processed")

    print("\n[3/4] Creating Postgres schema...")
    engine = get_db_engine()
    ok = create_schema(engine)
    if not ok:
        raise RuntimeError("Schema creation failed. Ensure sql/schema.sql exists.")
    print("✓ Schema created")

    print("\n[4/4] Load: MinIO processed -> Postgres ...")
    load_from_minio_processed(processed_bucket, engine)

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


