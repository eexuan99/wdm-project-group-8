import os
import psycopg2
import json
from kafka import KafkaConsumer, KafkaProducer
from flask import Flask

app = Flask("payment-consumer")

############################################ Data base set up ############################################

connector = psycopg2.connect(
    host=os.environ['POSTGRES_HOST'],
    database=os.environ['POSTGRES_DB'],
    user=os.environ['POSTGRES_USER'],
    password=os.environ['POSTGRES_PASSWORD'],
    port=os.environ['POSTGRES_PORT'])

cursor = connector.cursor()


############################################ Kafka set up ############################################
# TODO: finish
producer = KafkaProducer(
    bootstrap_servers = 'kafka-1.kafka-headless.default.svc.cluster.local:9092,kafka-0.kafka-headless.default.svc.cluster.local:9092,kafka-2.kafka-headless.default.svc.cluster.local:9092',
    value_serializer = lambda v: json.loads(v.decode('ascii')),
    key_serializer = lambda v: json.loads(v.decode('ascii')),
)

consumer = KafkaConsumer(
    #client_id = get it from k8s?,
    bootstrap_servers = 'kafka.default.svc.cluster.local:9092',
    group_id = 'pay_consumer',
    value_deserializer=lambda v: json.loads(v.decode('ascii')),
    key_deserializer=lambda v: json.loads(v.decode('ascii')),
    auto_offset_reset='earliest',
)

consumer.subscribe(topics=['Pay-topic'])

last_offsets = {}

############################################ Read Message loop ############################################

# TODO: put a try except around this loop to catch errors
for message in consumer:
    order_id, tr_num =  message.key['order_id'], message.key['tr_num']
    tr_type, user_id, amnt = message.value['tr_type'], message.value['user_id'], message.value['amnt'] 
    partition = message.partition

    # for every partition we store the last offset we've seen from that transistion only if it wasn't a duplicate message, else we store -1
    if partition not in last_offsets.keys(): last_offsets[partition] = -1

    # if we did not store the previous offset (rebalance or initializing)
    if message.offset != last_offsets[partition][1] + 1:
        sql_statement = """SELECT count(*) FROM messages 
                            WHERE order_id = %s and
                                transaction_number = %s and
                                sign = %s"""
        cursor.execute(sql_statement, (order_id, tr_num, tr_type))
        number = int(cursor.fetchone())
        
        # if message is a duplicate: continue to next message
        if number != 0:
            last_offsets[partition] = -1
            continue
        # else: save offset
        last_offsets[partition] = message.offset
    
    ok = False
    if tr_type == 'pay':
        try:
            sql_statement = """UPDATE payment
                                    SET credit = credit - %s
                                    WHERE user_id = %s and credit >= %s;"""

            cursor.execute(sql_statement, (amnt, user_id, amnt))
            if cursor.rowcount > 0:
                ok = True
                
        except Exception as err:
            connector.rollback()
            
    else:
        sql_statement = """UPDATE payment
                                    SET credit = credit + %s
                                    WHERE user_id = %s;"""
        cursor.execute(sql_statement, (amnt, user_id))

    sql_statement2 = """INSERT INTO messages(order_id, transaction_number, sign)
                                VALUES (%s, %s, %s);"""
    cursor.execute(sql_statement2, (order_id, tr_num, tr_type))
    connector.commit()

    if ok and tr_type == 'pay':
        producer.send(
                    'Outcomes-topic',
                    key = {
                        'order_id': order_id,
                        'tr_num': tr_num
                    },
                    value = {
                        'type': 'psucc',
                        'tr_type': tr_type,
                        'user_id': user_id,
                        'amnt': amnt
                    }
                )
    elif tr_type == 'pay':
        producer.send(
                'Outcomes-topic',
                key = {
                    'order_id': order_id,
                    'tr_num': tr_num
                },
                value = {
                    'type': 'pfail',
                    'tr_type': tr_type,
                    'user_id': user_id,
                    'amnt': amnt
                }
            )