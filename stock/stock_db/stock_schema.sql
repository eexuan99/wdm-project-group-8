CREATE TABLE IF NOT EXISTS stock (
    item_id SERIAL,
    stock int NOT NULL, 
    unit_price int NOT NULL CHECK (unit_price >= 0), 
    PRIMARY KEY (item_id)
);