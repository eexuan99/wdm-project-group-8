CREATE TABLE IF NOT EXISTS payment (
    user_id SERIAL,
    credit int NOT NULL CHECK (credit >= 0), 
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    order_id int,
    transaction_number int,
    sign char(3),
    PRIMARY KEY (order_id, transaction_number, sign)
);