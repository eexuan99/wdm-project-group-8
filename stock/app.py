import os
import atexit
import redis
import psycopg2
from flask import Flask

app = Flask("stock-service")

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


@app.post('/item/create/<price>')
def create_item(price: int): 
    sql_statement = """INSERT INTO stock (stock, unit_price) 
                       VALUES (%s, %s) RETURNING item_id;"""
    try:
        central_db_cursor.execute(sql_statement, (0, price))
        item_id_of_new_row = central_db_cursor.fetchone()[0]
        central_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Error creating item"}, 400
    
    return {"item_id": item_id_of_new_row}, 200


@app.get('/find/<item_id>')
def find_item(item_id: int):
    sql_statement = """SELECT * FROM stock WHERE item_id = %s;"""
    try:
        central_db_cursor.execute(sql_statement, (item_id,))
        item = central_db_cursor.fetchone()
        if not item:
            return {"error": "Item not found"}, 400
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Error creating item"}, 400
    
    return {"item_id": item[0], "stock": item[1],"price": item[2]}, 200


@app.post('/add/<item_id>/<amount>')
def add_stock(item_id: int, amount: int):
    sql_statement = """SELECT * FROM stock WHERE item_id = %s;"""
    try:
        central_db_cursor.execute(sql_statement, (item_id,))
        item = central_db_cursor.fetchone()
        if not item:
            return {"error": "Item not found"}, 400

        sql_statement = """UPDATE stock SET stock = stock + %s WHERE item_id = %s;"""
        central_db_cursor.execute(sql_statement, (amount, item_id))
        central_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Error creating item"}, 400
     
    return {"success": f"Added {amount} stock to item {item_id}"}, 200


@app.post('/subtract/<item_id>/<amount>')
def remove_stock(item_id: int, amount: int):
    sql_statement = """UPDATE stock SET stock = stock - %s WHERE item_id = %s AND stock >= %s;"""
    try:
        central_db_cursor.execute(sql_statement, (amount, item_id, amount))
        if central_db_cursor.rowcount > 0:
            central_db_conn.commit()
            return {"success": f"Removed {amount} stock from item {item_id}"}, 200
        else:
            return {"error": "Not enough stock or item not found"}, 400
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Error creating item"}, 400
    
