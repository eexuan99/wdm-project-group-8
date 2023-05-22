CREATE TYPE items AS (
    item_id int,
    amount int,
    unit_price int
);

CREATE TABLE IF NOT EXISTS order_table (
    order_id SERIAL,
    user_id int NOT NULL, 
    paid boolean NOT NULL,
    items items[] NOT NULL, 
    total_price int NOT NULL CHECK (total_price >= 0), 
    PRIMARY KEY (order_id)
);
