import json
import sys
from pathlib import Path

import pandas as pd


def extract_columns(raw_dir: str = "data/raw") -> dict:
    raw_path = Path(raw_dir)

    if not raw_path.exists() or not raw_path.is_dir():
        raise FileNotFoundError(f"Raw directory not found: {raw_path.resolve()}")

    csv_files = sorted(raw_path.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in: {raw_path.resolve()}")

    columns_map = {}

    for csv_path in csv_files:
        try:
            # nrows=0 reads only the header row (fast, doesn't load the whole file)
            df_head = pd.read_csv(csv_path, nrows=0)
            columns = df_head.columns.tolist()
            columns_map[csv_path.name] = columns
        except Exception as e:
            columns_map[csv_path.name] = {"ERROR": str(e)}

    return columns_map


def main():
    raw_dir = sys.argv[1] if len(sys.argv) > 1 else "data/raw"
    columns_map = extract_columns(raw_dir)

    # Print as a Python-dict-like JSON (easy to read/copy)
    print(json.dumps(columns_map, indent=2, ensure_ascii=False))

    # Also print a short summary
    print("\nSummary:")
    for fname, cols in columns_map.items():
        if isinstance(cols, dict) and "ERROR" in cols:
            print(f"  - {fname}: ERROR -> {cols['ERROR']}")
        else:
            print(f"  - {fname}: {len(cols)} columns")

if __name__ == "__main__":
    main()
