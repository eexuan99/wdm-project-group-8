import os
import atexit
import redis
import psycopg2
import re
from flask import Flask
from psycopg2 import sql

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
        central_db_cursor.execute(sql_statement, (order_id,))
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

        # Optional: this db access can be removed for making this app faster, 
        # the `update_order_items_query_add` already searches for the price
        # NOTE however that removing this will cause the error code of 400 to not be returned
        # Prof Asterios said that was ok though
        # Check if item exists and retrieve its price
        sql_statement = """SELECT unit_price FROM stock WHERE item_id = %s;"""
        central_db_cursor.execute(sql_statement, (item_id,))
        item = central_db_cursor.fetchone()
        if not item:
            return {"error": "Item not found"}, 400

        # price = item[0]
        update_order_items_query_add = sql.SQL("""
            UPDATE order_table  
            SET items = (
                SELECT CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM UNNEST(items) AS item
                        WHERE item.item_id = %s
                    )
                    THEN array_agg(
                        CASE
                            WHEN item.item_id = %s THEN ROW(item.item_id, item.amount + 1, item.unit_price)::items
                            ELSE item
                        END
                    )
                    ELSE CASE
                        WHEN (SELECT COUNT(*) FROM stock WHERE item_id = %s) > 0 THEN
                            array_agg(item) || (
                                SELECT (%s, 1, unit_price)::items
                                FROM stock
                                WHERE item_id = %s
                            )
                        ELSE
                            array_agg(item)
                        END
                END
                FROM UNNEST(items) AS item
            )
            WHERE order_id = %s;
        """)
        
        # Add item to order's items and update total price
        update_order_total_price_query = sql.SQL("""
                UPDATE order_table
                SET total_price = (
                    SELECT SUM((item.amount * item.unit_price))
                    FROM UNNEST(items) AS item
                )
                WHERE order_id = %s;
            """)
        
        central_db_cursor.execute(update_order_items_query_add, (item_id, item_id, item_id, item_id, item_id, order_id))
        central_db_cursor.execute(update_order_total_price_query, (order_id,))
        central_db_conn.commit()
        
        # sql_statement = """ UPDATE order_table
        #                     SET items = items || ROW(%s, 1, %s)::items, total_price = total_price + %s
        #                     WHERE order_id = %s; """
        # central_db_cursor.execute(sql_statement, (item_id, price, price, order_id))

        # central_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Something went wrong during adding an item"}, 500
    
    return {"success": f"Added item {item_id} to order {order_id}"}, 200


@app.delete('/removeItem/<order_id>/<item_id>')
def remove_item(order_id, item_id):
    # check if order exists
            # Check if order exists
    try:        
        sql_statement = """SELECT * FROM order_table WHERE order_id = %s;"""
        central_db_cursor.execute(sql_statement, (order_id,))
        order = central_db_cursor.fetchone()
        if not order:
            return {"error": "Order not found"}, 400

        # This step is OPTIONAL we can remove it to speed things up since db access is slow and expensive: 
        # Check if item exists and retrieve its price
        sql_statement = """SELECT unit_price FROM stock WHERE item_id = %s;"""
        central_db_cursor.execute(sql_statement, (item_id,))
        item = central_db_cursor.fetchone()
        if not item:
            return {"error": "Item with this item_id does not exist in stock table"}, 400
        
        # NOTE:TODO we do not yet check whether 
        # an item exists in the items[] array / shopping cart when we delete it

        update_order_items_query_remove = sql.SQL("""
            UPDATE order_table
            SET items = (
                SELECT array_remove(
                    array_agg(
                        CASE
                            WHEN item.item_id = %s AND item.amount > 1 THEN ROW(item.item_id, item.amount - 1, item.unit_price)::items
                            WHEN item.item_id = %s AND item.amount = 1 THEN NULL
                            ELSE item
                        END
                    ),
                    NULL
                )
                FROM UNNEST(items) AS item
            )
            WHERE order_id = %s;
        """)

        # Add item to order's items and update total price
        update_order_total_price_query = sql.SQL("""
                UPDATE order_table
                SET total_price = (
                    SELECT CASE WHEN array_length(items, 1) IS NULL THEN 0 ELSE SUM((item.amount * item.unit_price)) END
                    FROM UNNEST(items) AS item
                )
                WHERE order_id = %s;
            """)
        central_db_cursor.execute(update_order_items_query_remove, (item_id, item_id, order_id))
        central_db_cursor.execute(update_order_total_price_query, (order_id,))
        central_db_conn.commit()
    except psycopg2.DatabaseError as error:
        print(error)
        return {"error": "Failed to remove item from order"}, 400

    return {"success": f"Removed item {item_id} from order {order_id}"}, 200


@app.get('/find/<order_id>')
def find_order(order_id):
    try:
        sql_statement = """SELECT * FROM order_table WHERE order_id = %s;"""
        print(type(order_id))
        central_db_cursor.execute(sql_statement, (order_id,))
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
