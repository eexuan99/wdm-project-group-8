CREATE TYPE items AS (
    item_id int,
    amount int,
    unit_price int
);

CREATE TYPE payment_status as ENUM('not_paid', 'pending', 'paid');

CREATE TABLE IF NOT EXISTS order_table (
    order_id SERIAL,
    user_id int NOT NULL, 
    p_status payment_status NOT NULL,
    items items[] NOT NULL, 
    total_price int NOT NULL CHECK (total_price >= 0), 
    tr_number int DEFAULT 0,
    PRIMARY KEY (order_id)
);
