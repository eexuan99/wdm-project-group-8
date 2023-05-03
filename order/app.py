import os
import atexit

from flask import Flask
import redis
import psycopg2


gateway_url = os.environ['GATEWAY_URL']

app = Flask("order-service")

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

@app.post('/create/<user_id>')
def create_order(user_id):
    sql_statement = """INSERT INTO order_table (user_id, paid, items, total_price) 
                       VALUES (%s, %s, %s:items[], %s) RETURNING order_id;"""
    item = (1, 1, 0.99)
    items_list = [item]
    central_db_cursor.execute(sql_statement, (1, True, items_list, 0.99))
    order_id_of_new_row = central_db_cursor.fetchone()[0]
    central_db_conn.commit()
    return {"order_id": order_id_of_new_row}
    # pass


@app.delete('/remove/<order_id>')
def remove_order(order_id):
    pass


@app.post('/addItem/<order_id>/<item_id>')
def add_item(order_id, item_id):
    pass


@app.delete('/removeItem/<order_id>/<item_id>')
def remove_item(order_id, item_id):
    pass


@app.get('/find/<order_id>')
def find_order(order_id):
    pass


@app.post('/checkout/<order_id>')
def checkout(order_id):
    pass
