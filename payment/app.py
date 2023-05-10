import os
import atexit

import psycopg2
from flask import Flask
import redis


app = Flask("payment-service")

db: redis.Redis = redis.Redis(host=os.environ['REDIS_HOST'],
                              port=int(os.environ['REDIS_PORT']),
                              password=os.environ['REDIS_PASSWORD'],
                              db=int(os.environ['REDIS_DB']))

central_db_conn = psycopg2.connect(
    host=os.environ['POSTGRES_HOST'],
    database=os.environ['POSTGRES_DB'],
    user=os.environ['POSTGRES_USER'],
    password=os.environ['POSTGRES_PASSWORD'],
    port=os.environ['POSTGRES_PORT'])

central_db_cursor = central_db_conn.cursor()

def close_db_connection():
    db.close()
    central_db_cursor.close()
    central_db_conn.close()


atexit.register(close_db_connection)


@app.post('/create_user')
def create_user():
    sql_statement = """INSERT INTO payment (credit)
                       VALUES (%s) RETURNING user_id;"""
    central_db_cursor.execute(sql_statement, (0,))
    user_id = central_db_cursor.fetchone()[0]
    central_db_conn.commit()
    return {"user_id": user_id}
    # pass


@app.get('/find_user/<user_id>')
def find_user(user_id: str):
    sql_statement = """SELECT * FROM payment WHERE user_id = %s;"""
    central_db_cursor.execute(sql_statement, (user_id))
    user_id = central_db_cursor.fetchone()
    central_db_conn.commit()
    return {"user_id ": user_id}
    # pass


@app.post('/add_funds/<user_id>/<amount>')
def add_credit(user_id: str, amount: int):
    sql_statement = """UPDATE payment
                       SET credit = credit + %s
                       WHERE user_id = %s;"""
    central_db_cursor.execute(sql_statement, (amount, user_id))
    central_db_conn.commit()
    return {"success": f"Added {amount} of credit to user {user_id}"}
    # pass

# Dont understand why there is order_id here ..
@app.post('/pay/<user_id>/<order_id>/<amount>')
def remove_credit(user_id: str, order_id: str, amount: int):
    sql_statement = """UPDATE payment
                           SET credit = credit - %s
                           WHERE user_id = %s;"""
    central_db_cursor.execute(sql_statement, (amount, user_id))
    central_db_conn.commit()
    return {"success": f"Subtracted {amount} of credit to user {user_id}"}
    # pass

### Should we have a column for cancelled?
@app.post('/cancel/<user_id>/<order_id>')
def cancel_payment(user_id: str, order_id: str):
    # sql_statement = """UPDATE order_id
    #                     SET cancel = TRUE
    #                     WHERE payment.user_id = %s AND order_table.user_id = %s AND order_table.order_id = %s"""
    # central_db_cursor.execute(sql_statement, (user_id, user_id, order_id))
    # orderid = central_db_cursor.fetchone()[0]
    # central_db_conn.commit()
    # return {"Order cancelled: ": orderid}
    pass


@app.post('/status/<user_id>/<order_id>')
def payment_status(user_id: str, order_id: str):
    sql_statement = """SELECT * FROM order_table WHERE payment.user_id = %s AND order_table.user_id = %s AND order_table.order_id = %s"""
    central_db_cursor.execute(sql_statement, (user_id, user_id, order_id))
    paid = central_db_cursor.fetchone()[2]
    central_db_conn.commit()
    return {"Payment has been paid ": paid}
