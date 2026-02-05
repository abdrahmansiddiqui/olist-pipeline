from minio import Minio
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

def upload_raw_csvs():
    '''Upload raw CSV files to MinIO'''
    
    # Initialize MinIO client
    client = Minio(
        os.getenv('MINIO_ENDPOINT'),
        access_key=os.getenv('MINIO_ACCESS_KEY'),
        secret_key=os.getenv('MINIO_SECRET_KEY'),
        secure=False
    )
    
    bucket = os.getenv('MINIO_BUCKET_RAW')
    
    # Create bucket if it doesn't exist
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print(f'✓ Created bucket: {bucket}')
    else:
        print(f'✓ Bucket already exists: {bucket}')
    
    # Upload all CSV files
    raw_dir = Path('data/raw')
    csv_files = list(raw_dir.glob('*.csv'))
    
    print(f'\nUploading {len(csv_files)} CSV files to MinIO...')
    
    for csv_path in csv_files:
        object_name = csv_path.name
        client.fput_object(bucket, object_name, str(csv_path))
        print(f'  ✓ Uploaded: {object_name}')
    
    print(f'\n✓ All files uploaded to bucket \'{bucket}\'')
    
    # List objects to verify
    objects = client.list_objects(bucket)
    print(f'\nFiles in bucket:')
    for obj in objects:
        print(f'  - {obj.object_name} ({obj.size:,} bytes)')

if __name__ == '__main__':
    upload_raw_csvs()
