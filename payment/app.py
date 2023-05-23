import os
import atexit
import redis
import psycopg2
from flask import Flask

app = Flask("payment-service")

db: redis.Redis = redis.Redis(host=os.environ['REDIS_HOST'],
                              port=int(os.environ['REDIS_PORT']),
                              password=os.environ['REDIS_PASSWORD'],
                              db=int(os.environ['REDIS_DB']))

order_db_conn = psycopg2.connect(
    host=os.environ['POSTGRES_HOST_ORDER'],
    database=os.environ['POSTGRES_DB'],
    user=os.environ['POSTGRES_USER'],
    password=os.environ['POSTGRES_PASSWORD'],
    port=os.environ['POSTGRES_PORT'])

order_db_cursor = order_db_conn.cursor()

payment_db_conn = psycopg2.connect(
    host=os.environ['POSTGRES_HOST_PAYMENT'],
    database=os.environ['POSTGRES_DB'],
    user=os.environ['POSTGRES_USER'],
    password=os.environ['POSTGRES_PASSWORD'],
    port=os.environ['POSTGRES_PORT'])

payment_db_cursor = payment_db_conn.cursor()

def close_db_connection():
    db.close()
    order_db_cursor.close()
    order_db_conn.close()
    payment_db_cursor.close()
    payment_db_conn.close()

atexit.register(close_db_connection)

# Just a simple get all function so we can use this instead of pgadmin
@app.get('/getall')
def get_all():
    sql_statement = """SELECT * FROM payment;"""
    payment_db_cursor.execute(sql_statement)
    user = payment_db_cursor.fetchall()    
    return {"user": user}, 200


@app.post('/create_user')
def create_user():
    sql_statement = """INSERT INTO payment (credit)
                       VALUES (%s) RETURNING user_id;"""
    try:
        payment_db_cursor.execute(sql_statement, (0,))
        user_id = payment_db_cursor.fetchone()[0]
        payment_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Error creating user"}, 400
    
    return {"user_id": user_id}, 200


@app.get('/find_user/<user_id>')
def find_user(user_id: str):
    sql_statement = """SELECT * FROM payment WHERE user_id = %s;"""
    try:
        payment_db_cursor.execute(sql_statement, (user_id,))
        user = payment_db_cursor.fetchone()
        if not user:
            return {"error": "User not found"}, 400
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Error finding user"}, 400

    return {"user_id": user[0], "credit": user[1]}, 200


@app.post('/add_funds/<user_id>/<amount>')
def add_credit(user_id: str, amount: int):
    try:
        # Checking if user exist
        sql_statement = """SELECT * FROM payment WHERE user_id = %s;"""
        payment_db_cursor.execute(sql_statement, (user_id,))
        user = payment_db_cursor.fetchone()
        if not user:
            return {"error": "User not found"}, 400
        
        # Adding credit
        sql_statement = """ UPDATE payment
                            SET credit = credit + %s
                            WHERE user_id = %s; """
        payment_db_cursor.execute(sql_statement, (amount, user_id))
        payment_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Error finding user or adding credit"}, 400

    return {"success": f"Added {amount} of credit to user {user_id}"}, 200


# Dont understand why there is order_id here ..
@app.post('/pay/<user_id>/<order_id>/<amount>')
def remove_credit(user_id: str, order_id: str, amount: int):
    try:
        # Checking if user exist
        sql_statement = """SELECT * FROM payment WHERE user_id = %s;"""
        payment_db_cursor.execute(sql_statement, (user_id,))
        user = payment_db_cursor.fetchone()
        if not user:
            return {"error": "User not found"}, 400
        
        # Subtracting credit
        sql_statement = """UPDATE payment
                            SET credit = credit - %s
                            WHERE user_id = %s;"""
        payment_db_cursor.execute(sql_statement, (amount, user_id))
        payment_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Error finding user or adding credit"}, 400

    return {"success": f"Subtracted {amount} of credit to user {user_id}"}, 200


@app.post('/cancel/<user_id>/<order_id>')
def cancel_payment(user_id: str, order_id: str):
    sql_statement = """UPDATE order_table
                        SET status = 'cancelled'
                        WHERE user_id = %s AND order_id = %s;"""
    try: 
        order_db_cursor.execute(sql_statement, (user_id, order_id))
        order_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Error cancelling payment"}, 400
    
    return {"success": f"Order {order_id} cancelled"}, 200


@app.post('/status/<user_id>/<order_id>')
def payment_status(user_id: str, order_id: str):
    sql_statement = """SELECT status FROM order_table WHERE user_id = %s AND order_id = %s;"""
    try: 
        order_db_cursor.execute(sql_statement, (user_id, order_id))
        status = order_db_cursor.fetchone()
        if not status:
            return {"error": "Order not found"}, 400
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Error cancelling payment"}, 400
    
    return {"Order status": status[0]}, 200
