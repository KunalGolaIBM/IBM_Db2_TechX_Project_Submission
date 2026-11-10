CREATE TABLE customers (
    id INTEGER NOT NULL,
    name VARCHAR(100),
    email VARCHAR(150),
    country VARCHAR(2),
    signup_date DATE,
    credit_limit DECIMAL(10, 2),
    active BOOLEAN
);

CREATE TABLE products (
    id INTEGER NOT NULL,
    name VARCHAR(100),
    category VARCHAR(50),
    price DECIMAL(10, 2),
    stock INTEGER,
    discontinued BOOLEAN
);

CREATE TABLE orders (
    id INTEGER NOT NULL,
    customer_id INTEGER,
    order_date DATE,
    status VARCHAR(20),
    total DECIMAL(12, 2),
    shipped BOOLEAN
);

CREATE TABLE order_items (
    id INTEGER NOT NULL,
    order_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    unit_price DECIMAL(10, 2),
    discount DECIMAL(5, 2)
);
