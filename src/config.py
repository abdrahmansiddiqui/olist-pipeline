from __future__ import annotations

# Exact filenames we expect in MinIO raw bucket (and/or data/raw)
FILE_TO_DATASET = {
    "olist_customers_dataset.csv": "customers",
    "olist_sellers_dataset.csv": "sellers",
    "olist_products_dataset.csv": "products",
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_geolocation_dataset.csv": "geolocation",
    "product_category_name_translation.csv": "product_category_name_translation",
}

# Primary keys + foreign keys (matches your SQL schema)
DATA_MODEL = {
    "customers": {
        "primary_key": ["customer_id"],
        "foreign_keys": {},
    },
    "sellers": {
        "primary_key": ["seller_id"],
        "foreign_keys": {},
    },
    "product_category_name_translation": {
        "primary_key": ["product_category_name"],
        "foreign_keys": {},
    },
    "products": {
        "primary_key": ["product_id"],
        "foreign_keys": {
            "product_category_name": ("product_category_name_translation", "product_category_name")
        },
    },
    "orders": {
        "primary_key": ["order_id"],
        "foreign_keys": {
            "customer_id": ("customers", "customer_id")
        },
    },
    "order_items": {
        "primary_key": ["order_id", "order_item_id"],
        "foreign_keys": {
            "order_id": ("orders", "order_id"),
            "product_id": ("products", "product_id"),
            "seller_id": ("sellers", "seller_id"),
        },
    },
    "order_payments": {
        "primary_key": ["order_id", "payment_sequential"],
        "foreign_keys": {
            "order_id": ("orders", "order_id")
        },
    },
    "order_reviews": {
        "primary_key": ["review_id"],
        "foreign_keys": {
            "order_id": ("orders", "order_id")
        },
    },
    "geolocation": {
        "primary_key": None,
        "foreign_keys": {},
    },
}

# Force ZIP prefix columns to be strings to avoid 12345.0 / losing leading zeros
DTYPE_MAP = {
    "customers": {
        "customer_zip_code_prefix": "string",
        "customer_state": "string",
        "customer_city": "string",
    },
    "sellers": {
        "seller_zip_code_prefix": "string",
        "seller_state": "string",
        "seller_city": "string",
    },
    "geolocation": {
        "geolocation_zip_code_prefix": "string",
        "geolocation_city": "string",
        "geolocation_state": "string",
    },
    # Others can be inferred safely
}

# Explicit date columns per dataset (stabilizes parsing and prevents surprises)
DATE_COLS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "order_reviews": ["review_creation_date", "review_answer_timestamp"],
}
