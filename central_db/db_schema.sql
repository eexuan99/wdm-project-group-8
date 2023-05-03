CREATE TYPE items AS (
    item_id int,
    amount int,
    unit_price NUMERIC(255, 2)
);

CREATE TABLE IF NOT EXISTS payment (
    user_id SERIAL,
    credit NUMERIC(255, 2) CHECK (credit >= 0), 
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS stock (
    item_id SERIAL,
    stock int NOT NULL, 
    unit_price NUMERIC(255, 2) CHECK (unit_price >= 0), 
    PRIMARY KEY (item_id)
);

CREATE TABLE IF NOT EXISTS order_table (
    order_id SERIAL,
    user_id int NOT NULL REFERENCES payment, 
    paid boolean NOT NULL,
    items items[] NOT NULL, 
    total_price NUMERIC(255, 2) CHECK (total_price >= 0), 
    PRIMARY KEY (order_id)
);

-- INSERT INTO payment VALUES (value1, value2, value3, ...); 
INSERT INTO payment (credit) VALUES (10); 
INSERT INTO stock (stock, unit_price) VALUES (999, 0.99);
-- INSERT INTO order_table (user_id, paid, items, total_price) VALUES (1, true, ARRAY[(1, 1, 0.99)::items], 0.99);
