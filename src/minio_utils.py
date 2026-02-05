from __future__ import annotations

import io
import os
import time
from dotenv import load_dotenv
from minio import Minio

load_dotenv()

def get_minio_client() -> Minio:
    endpoint = os.getenv("MINIO_ENDPOINT")
    access_key = os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET_KEY")
    if not endpoint or not access_key or not secret_key:
        raise RuntimeError("Missing MinIO env vars. Check .env (MINIO_ENDPOINT/MINIO_ACCESS_KEY/MINIO_SECRET_KEY).")

    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
    )

def ensure_bucket(client: Minio, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

def wait_for_minio(timeout_seconds: int = 60) -> None:
    client = get_minio_client()
    start = time.time()
    while True:
        try:
            client.list_buckets()
            return
        except Exception as e:
            if time.time() - start > timeout_seconds:
                raise RuntimeError(f"MinIO not ready after {timeout_seconds}s: {e}")
            time.sleep(2)

def download_object_bytes(client: Minio, bucket: str, object_name: str) -> bytes:
    resp = client.get_object(bucket, object_name)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()

def upload_bytes(client: Minio, bucket: str, object_name: str, data: bytes, content_type: str = "text/csv") -> None:
    bio = io.BytesIO(data)
    client.put_object(bucket, object_name, bio, length=len(data), content_type=content_type)
