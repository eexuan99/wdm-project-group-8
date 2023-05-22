CREATE TABLE IF NOT EXISTS payment (
    user_id SERIAL,
    credit int NOT NULL CHECK (credit >= 0), 
    PRIMARY KEY (user_id)
);
