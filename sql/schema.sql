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
