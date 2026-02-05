# Olist Data Pipeline (Kaggle -> MinIO -> ETL -> Postgres)

## Requirements
- Docker Desktop
- Python 3.11
- uv (optional) or pip

## Setup
1) Start services:
   docker compose up -d

2) Create .env
   Copy .env.example -> .env and fill values

3) Run pipeline:
   python src/run_pipeline.py

## Services
- MinIO Console: http://localhost:9001
- pgAdmin: http://localhost:5050
- Postgres: localhost:5432
