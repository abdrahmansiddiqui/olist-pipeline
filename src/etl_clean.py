from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from config import FILE_TO_DATASET, DATA_MODEL, DTYPE_MAP, DATE_COLS
from minio_utils import get_minio_client, ensure_bucket, download_object_bytes, upload_bytes

load_dotenv()

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
UNKNOWN_CATEGORY_KEY = "unknown"
UNKNOWN_CATEGORY_EN = "Unknown"

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.lower().str.replace(" ", "_")
    # Fix Olist typo in products: "lenght" -> "length"
    df.columns = df.columns.str.replace("lenght", "length", regex=False)
    return df

def _clean_zip_prefix(series: pd.Series) -> pd.Series:
    s = series.astype("string")
    s = s.str.replace(r"\.0$", "", regex=True).str.strip()
    s = s.replace("", pd.NA)
    return s

def clean_dataframe(df: pd.DataFrame, dataset_name: str, rejected_dir: Path) -> pd.DataFrame:
    print(f"\nCleaning {dataset_name} | original shape: {df.shape}")

    df = _normalize_columns(df)

    # Replace common missing markers with real nulls
    df = df.replace("", pd.NA).replace("nan", pd.NA).replace(np.nan, pd.NA)

    # Enforce zip prefix columns as strings (prevents 12345.0)
    if dataset_name in ("customers", "sellers", "geolocation"):
        for col in df.columns:
            if col.endswith("_zip_code_prefix") or col == "geolocation_zip_code_prefix":
                df[col] = _clean_zip_prefix(df[col])

    # Normalize state fields if present
    for col in ("customer_state", "seller_state", "geolocation_state"):
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip().str.upper().replace("", pd.NA)

    # Convert known date columns explicitly
    for col in DATE_COLS.get(dataset_name, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            print(f"  ✓ Parsed datetime: {col}")

    # Primary key handling (supports composite keys)
    model = DATA_MODEL.get(dataset_name)
    if model and model["primary_key"]:
        pk_cols = model["primary_key"]

        # Drop rows with NULL PK parts (DB will reject them)
        before = len(df)
        df = df.dropna(subset=pk_cols)
        dropped = before - len(df)
        if dropped:
            print(f"  ⚠ Dropped {dropped:,} rows with NULL PK parts: {pk_cols}")

        # Quarantine duplicate review rows (you requested)
        if dataset_name == "order_reviews":
            dup_mask = df.duplicated(subset=pk_cols, keep="first")
            dup_df = df[dup_mask].copy()
            if len(dup_df):
                out = rejected_dir / "order_reviews_duplicate_review_id.csv"
                dup_df.to_csv(out, index=False, date_format=DATE_FORMAT)
                print(f"  ⚠ Saved {len(dup_df):,} duplicate review rows -> {out}")

        # Deduplicate strictly on PK
        before = len(df)
        df = df.drop_duplicates(subset=pk_cols, keep="first")
        deduped = before - len(df)
        if deduped:
            print(f"  ✓ Removed {deduped:,} duplicate rows on PK {pk_cols}")

    # For geolocation: remove exact duplicate rows (safe)
    if dataset_name == "geolocation":
        before = len(df)
        df = df.drop_duplicates(keep="first")
        removed = before - len(df)
        if removed:
            print(f"  ✓ Removed {removed:,} exact duplicate geolocation rows")

    print(f"  Final shape: {df.shape}")
    return df

def validate_primary_keys(dfs: dict[str, pd.DataFrame]) -> bool:
    print("\n" + "=" * 70)
    print("VALIDATING PRIMARY KEYS")
    print("=" * 70)

    ok = True
    for dataset_name, model in DATA_MODEL.items():
        if dataset_name not in dfs:
            continue
        pk_cols = model["primary_key"]
        if pk_cols is None:
            print(f"{dataset_name}: (no PK) OK")
            continue

        df = dfs[dataset_name]
        missing = [c for c in pk_cols if c not in df.columns]
        if missing:
            print(f"{dataset_name}: ❌ missing PK columns {missing}")
            ok = False
            continue

        nulls = {c: int(df[c].isna().sum()) for c in pk_cols}
        dups = int(df.duplicated(subset=pk_cols).sum())
        if any(nulls.values()) or dups:
            print(f"{dataset_name}: ❌ PK issues | nulls={nulls} | duplicates={dups}")
            ok = False
        else:
            print(f"{dataset_name}: ✓ PK OK ({len(df):,} rows)")
    return ok

def validate_foreign_keys(dfs: dict[str, pd.DataFrame]) -> bool:
    print("\n" + "=" * 70)
    print("VALIDATING FOREIGN KEYS")
    print("=" * 70)

    ok = True
    for child, model in DATA_MODEL.items():
        if child not in dfs:
            continue
        for fk_col, (parent, parent_col) in model["foreign_keys"].items():
            if parent not in dfs:
                print(f"{child}.{fk_col} -> {parent}.{parent_col}: ⚠ parent not loaded")
                continue

            child_df = dfs[child]
            parent_df = dfs[parent]

            if fk_col not in child_df.columns:
                print(f"{child}.{fk_col}: ❌ missing FK column")
                ok = False
                continue
            if parent_col not in parent_df.columns:
                print(f"{parent}.{parent_col}: ❌ missing parent column")
                ok = False
                continue

            fk_vals = set(child_df[fk_col].dropna().unique())
            parent_vals = set(parent_df[parent_col].dropna().unique())
            orphans = fk_vals - parent_vals
            if orphans:
                orphan_rows = int(child_df[child_df[fk_col].isin(orphans)].shape[0])
                print(f"{child}.{fk_col} -> {parent}.{parent_col}: ❌ {orphan_rows:,} orphan rows ({len(orphans)} invalid keys)")
                ok = False
            else:
                print(f"{child}.{fk_col} -> {parent}.{parent_col}: ✓ OK")
    return ok

def process_from_minio(raw_bucket: str, processed_bucket: str, processed_dir: str = "data/processed") -> dict[str, pd.DataFrame]:
    client = get_minio_client()
    ensure_bucket(client, raw_bucket)
    ensure_bucket(client, processed_bucket)

    Path(processed_dir).mkdir(parents=True, exist_ok=True)
    rejected_dir = Path("data/rejected")
    rejected_dir.mkdir(parents=True, exist_ok=True)

    raw_objects = [obj.object_name for obj in client.list_objects(raw_bucket, recursive=True)]
    dataset_to_file = {v: k for k, v in FILE_TO_DATASET.items()}

    dataset_order = [
        "product_category_name_translation",
        "customers",
        "sellers",
        "products",
        "orders",
        "order_items",
        "order_payments",
        "order_reviews",
        "geolocation",
    ]
    targets = [dataset_to_file[d] for d in dataset_order if dataset_to_file.get(d) in raw_objects]

    print("=" * 80)
    print("TRANSFORM STEP: MinIO raw -> cleaned -> local processed + MinIO processed")
    print("=" * 80)
    print(f"Found {len(targets)} expected CSV objects in MinIO raw bucket.")

    dfs: dict[str, pd.DataFrame] = {}

    for filename in targets:
        dataset_name = FILE_TO_DATASET[filename]
        print(f"\nDownloading from MinIO: {filename} -> dataset={dataset_name}")

        data = download_object_bytes(client, raw_bucket, filename)
        dtype = DTYPE_MAP.get(dataset_name)
        df = pd.read_csv(io.BytesIO(data), dtype=dtype)

        df_clean = clean_dataframe(df, dataset_name, rejected_dir)

        # 1) Ensure translation table contains an "unknown" category row
        if dataset_name == "product_category_name_translation":
            if "product_category_name" in df_clean.columns and "product_category_name_english" in df_clean.columns:
                exists = (df_clean["product_category_name"].astype("string") == UNKNOWN_CATEGORY_KEY).any()
                if not exists:
                    df_clean = pd.concat(
                        [
                            df_clean,
                            pd.DataFrame(
                                {
                                    "product_category_name": [UNKNOWN_CATEGORY_KEY],
                                    "product_category_name_english": [UNKNOWN_CATEGORY_EN],
                                }
                            ),
                        ],
                        ignore_index=True,
                    )
                    print(f"  ✓ Added translation row: {UNKNOWN_CATEGORY_KEY} -> {UNKNOWN_CATEGORY_EN}")

                # Ensure no duplicate PKs after adding
                df_clean = df_clean.drop_duplicates(subset=["product_category_name"], keep="first")

        # 2) For products: replace invalid categories with "unknown" (and quarantine originals)
        if dataset_name == "products" and "product_category_name_translation" in dfs:
            trans = dfs["product_category_name_translation"]
            valid = set(trans["product_category_name"].dropna().astype("string").unique())

            if "product_category_name" in df_clean.columns:
                cat = df_clean["product_category_name"].astype("string")
                bad_mask = cat.notna() & (cat != "") & ~cat.isin(valid)

                if bad_mask.any():
                    bad_df = df_clean[bad_mask].copy()
                    bad_df.insert(0, "replaced_with", UNKNOWN_CATEGORY_KEY)
                    out = rejected_dir / "products_invalid_category_replaced.csv"
                    bad_df.to_csv(out, index=False, date_format=DATE_FORMAT)

                    # Also save a small summary of which category values were invalid
                    summary = bad_df["product_category_name"].value_counts(dropna=True).rename_axis("invalid_category").reset_index(name="count")
                    summary_out = rejected_dir / "invalid_product_categories_summary.csv"
                    summary.to_csv(summary_out, index=False)

                    df_clean.loc[bad_mask, "product_category_name"] = UNKNOWN_CATEGORY_KEY

                    print(f"  ⚠ Replaced {int(bad_mask.sum()):,} products' invalid categories with '{UNKNOWN_CATEGORY_KEY}'")
                    print(f"  ⚠ Saved details -> {out}")
                    print(f"  ⚠ Saved summary -> {summary_out}")

        dfs[dataset_name] = df_clean

        # Save locally + upload processed
        out_local = Path(processed_dir) / f"{dataset_name}_clean.csv"
        df_clean.to_csv(out_local, index=False, date_format=DATE_FORMAT)
        out_bytes = df_clean.to_csv(index=False, date_format=DATE_FORMAT).encode("utf-8")
        upload_bytes(client, processed_bucket, f"{dataset_name}_clean.csv", out_bytes)

        print(f"  ✓ Saved local: {out_local}")
        print(f"  ✓ Uploaded to MinIO processed: {dataset_name}_clean.csv")

    pk_ok = validate_primary_keys(dfs)
    fk_ok = validate_foreign_keys(dfs)

    print("\n" + "=" * 80)
    print(f"TRANSFORM SUMMARY | PK OK: {'YES' if pk_ok else 'NO'} | FK OK: {'YES' if fk_ok else 'NO'}")
    print("=" * 80)

    return dfs

if __name__ == "__main__":
    raw_bucket = os.getenv("MINIO_BUCKET_RAW", "olist-raw")
    processed_bucket = os.getenv("MINIO_BUCKET_PROCESSED", "olist-processed")
    process_from_minio(raw_bucket, processed_bucket, "data/processed")
