CREATE TABLE recalltrace_products (
    product_code VARCHAR(40) NOT NULL PRIMARY KEY,
    product_name VARCHAR(120) NOT NULL
);

CREATE TABLE recalltrace_inventory (
    product_code VARCHAR(40) NOT NULL,
    lot_code VARCHAR(40) NOT NULL,
    site VARCHAR(80) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    PRIMARY KEY (product_code, lot_code, site),
    FOREIGN KEY (product_code) REFERENCES recalltrace_products (product_code)
);
