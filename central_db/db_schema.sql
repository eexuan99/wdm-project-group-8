CREATE TYPE items AS (
    item_id int,
    amount int,
    unit_price int
);

CREATE TABLE IF NOT EXISTS payment (
    user_id SERIAL,
    credit int NOT NULL CHECK (credit >= 0), 
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS stock (
    item_id SERIAL,
    stock int NOT NULL, 
    unit_price int NOT NULL CHECK (unit_price >= 0), 
    PRIMARY KEY (item_id)
);

CREATE TABLE IF NOT EXISTS order_table (
    order_id SERIAL,
    user_id int NOT NULL REFERENCES payment, 
    paid boolean NOT NULL,
    items items[] NOT NULL, 
    total_price int NOT NULL CHECK (total_price >= 0), 
    PRIMARY KEY (order_id)
);

-- CREATE OR REPLACE FUNCTION f_array_remove_elem1(anyarray, anyelement)
--   RETURNS anyarray LANGUAGE sql IMMUTABLE AS
-- 'SELECT $1[:idx-1] || $1[idx+1:] FROM array_position($1, $2) idx';
-- INSERT INTO payment VALUES (value1, value2, value3, ...); 
INSERT INTO payment (credit) VALUES (10); 
INSERT INTO stock (stock, unit_price) VALUES (999, 0.99);
INSERT INTO order_table (user_id, paid, items, total_price) VALUES (1, true, ARRAY[(1, 1, 0.99)::items], 0.99);

