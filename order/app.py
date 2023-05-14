import os
import atexit
import redis
import psycopg2
import re
from flask import Flask

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
                       VALUES (%s, %s, %s::items[], %s) RETURNING order_id;"""
    try:
        central_db_cursor.execute(sql_statement, (user_id, False, [], 0))
        order_id_of_new_row = central_db_cursor.fetchone()[0]
        central_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "User id not found"}, 400
    
    return {"order_id": order_id_of_new_row}, 200


@app.delete('/remove/<order_id>')
def remove_order(order_id):
    sql_statement = """ DELETE FROM order_table
                        WHERE order_id=%s; """
    try:
        central_db_cursor.execute(sql_statement, (order_id))
        central_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Order id not found"}, 400
    
    return {'success': f"Removed order {order_id}"}, 200


@app.post('/addItem/<order_id>/<item_id>')
def add_item(order_id, item_id):
    try:
        # Check if order exists
        sql_statement = """SELECT * FROM order_table WHERE order_id = %s;"""
        central_db_cursor.execute(sql_statement, (order_id,))
        order = central_db_cursor.fetchone()
        if not order:
            return {"error": "Order not found"}, 400

        # Check if item exists and retrieve its price
        sql_statement = """SELECT unit_price FROM stock WHERE item_id = %s;"""
        central_db_cursor.execute(sql_statement, (item_id,))
        item = central_db_cursor.fetchone()
        if not item:
            return {"error": "Item not found"}, 400

        price = item[0]

        # Add item to order's items and update total price
        sql_statement = """ UPDATE order_table
                            SET items = items || ROW(%s, 1, %s)::items, total_price = total_price + %s
                            WHERE order_id = %s; """
        central_db_cursor.execute(sql_statement, (item_id, price, price, order_id))

        central_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Something went wrong during checkout"}, 500
    
    return {"success": f"Added item {item_id} to order {order_id}"}, 200


@app.delete('/removeItem/<order_id>/<item_id>')
def remove_item(order_id, item_id):
    # Fetch the items array from the order
    central_db_cursor.execute("SELECT items FROM order_table WHERE order_id = %s", (order_id,))
    items = central_db_cursor.fetchone()[0]

    # Find the item in the array
    item_index = None
    for index, item in enumerate(parse_items(items)):
        if int(item[0]) == int(item_id):
            item_index = index
            break

    if item_index is None:
        return {"error": "Item not in order"}, 400  

    # Get the amount and unit_price of the item
    _, amount, unit_price = parse_items(items)[item_index]

    try:
        if amount > 1:
            # If the item's amount is more than 1, decrement the amount
            sql_statement = """ UPDATE order_table 
                                SET items = items[:item_index] || items[item_index + 1:] 
                                WHERE order_id = %s; """
            central_db_cursor.execute(sql_statement, (order_id,))
        else:
            # If the item's amount is 1, remove the item from the array
            sql_statement = """ UPDATE order_table 
                                SET items = array_remove(items, ROW(%s, 1, %s)::items) 
                                WHERE order_id = %s; """
            central_db_cursor.execute(sql_statement, (item_id, unit_price, order_id,))

        # Subtract the item's unit_price from the order's total_price
        sql_statement = """ UPDATE order_table 
                            SET total_price = total_price - %s 
                            WHERE order_id = %s; """
        central_db_cursor.execute(sql_statement, (unit_price, order_id,))

        central_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Failed to remove item from order"}, 400

    return {"success": f"Removed item {item_id} from order {order_id}"}, 200


@app.get('/find/<order_id>')
def find_order(order_id):
    try:
        sql_statement = """SELECT * FROM order_table WHERE order_id = %s;"""
        central_db_cursor.execute(sql_statement, (order_id))
        order = central_db_cursor.fetchone()
        if not order:
            return {"error": "order not found"}, 400
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Order not found"}, 400
    
    return {"order_id": order[0], "user_id": order[1], "paid": order[2],
            "items": parse_items(order[3]), "total_price": order[4]}, 200


@app.post('/checkout/<order_id>')
def checkout(order_id):
    try:
        sql_statement = """SELECT user_id, total_price, items FROM order_table WHERE order_id = %s;"""
        central_db_cursor.execute(sql_statement, (order_id,))
        order = central_db_cursor.fetchone()
        if not order:
            return {"error": "Order not found"}, 400

        user_id, total_price, items_string = order
        items = parse_items(items_string)

        # Check if user has enough credit
        sql_statement = """SELECT credit FROM payment WHERE user_id = %s;"""
        central_db_cursor.execute(sql_statement, (user_id,))
        credit = central_db_cursor.fetchone()[0]
        if credit < total_price:
            return {"error": "Not enough credit"}, 400

        # Subtract total price from user's credit
        sql_statement = """UPDATE payment SET credit = credit - %s WHERE user_id = %s;"""
        central_db_cursor.execute(sql_statement, (total_price, user_id))

        # Subtract quantities from stock
        for item_id, stock, _ in items:
            sql_statement = """UPDATE stock SET stock = stock - %s WHERE item_id = %s;"""
            central_db_cursor.execute(sql_statement, (stock, item_id))

        # Mark order as paid
        sql_statement = """UPDATE order_table SET paid = TRUE WHERE order_id = %s;"""
        central_db_cursor.execute(sql_statement, (order_id,))

        central_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Something went wrong during checkout"}, 500
    
    return {"success": f"Order {order_id} has been paid"}, 200



def parse_items(items_str):
    items_str = items_str[1:-1]
    items_list = items_str.split(",")
    items = []
    for i, j, k in zip(items_list[0::3], items_list[1::3], items_list[2::3]):
        items.append((parse_integer(i), parse_integer(j), parse_integer(k)))
    return items


def parse_integer(str):
    return int(re.sub("[^0-9]", "", str))
