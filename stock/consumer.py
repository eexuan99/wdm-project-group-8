import os
import psycopg2
import json
from kafka import KafkaConsumer, KafkaProducer
from flask import Flask

app = Flask("stock-consumer")

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
    value_serializer = lambda v: json.dumps(v).encode('ascii'),
    key_serializer = lambda v: json.dumps(v).encode('ascii'),
)

consumer = KafkaConsumer(
    #client_id = get it from k8s?,
    bootstrap_servers = 'kafka.default.svc.cluster.local:9092',
    group_id = 'stock_consumer',
    value_deserializer=lambda v: json.loads(v.decode('ascii')),
    key_deserializer=lambda v: json.loads(v.decode('ascii')),
    auto_offset_reset='earliest',
)

consumer.subscribe(topics=['Stock-topic'])

last_offsets = {}

############################################ Read Message loop ############################################

# TODO: put a try except around this loop to catch errors
for message in consumer:
    print(f"message key is {message.key} , message keys order id  = {message.key['order_id']}, message key's tr_num is = {message.key['tr_num']}")
    print(f"message keys order id type = {type(message.key['order_id'])}, message key's tr_num is = {type(message.key['tr_num'])}")
    order_id, tr_num =  message.key['order_id'], message.key['tr_num'] # for some reason tr_num is of type list, it is a list of 1 element so I'll get that 1 element
    # TODO remove the if stament below:
    # if len(message.key['tr_num']) != 1:
    #     raise Exception(f"Unexpected: message.key['tr_num'] is not a list with only one element instead it has the following contents {message.key['tr_num']}")
    tr_type, items = message.value['type'], message.value['items'] 
    print(f"the message values are tr_type= {tr_type} and items = {items}")
    partition = message.partition

    # for every partition we store the last offset we've seen from that transistion only if it wasn't a duplicate message, else we store -1
    if partition not in last_offsets.keys(): last_offsets[partition] = -1

    # if we did not store the previous offset (rebalance or initializing)
    if message.offset != last_offsets[partition] + 1:
        sql_statement = """SELECT count(*) FROM messages 
                            WHERE order_id = %s and
                                transaction_number = %s and
                                sign = %s"""
        cursor.execute(sql_statement, (order_id, tr_num, tr_type))
        ret  = cursor.fetchone()
        print(f'ret: {ret}')
        print(f'type of ret is {type(ret)}')
        number = ret[0]
        
        # if message is a duplicate: continue to next message
        if number != 0:
            last_offsets[partition] = -1
            print("did not do anything with this message: if loop at line 72")
            continue
        # else: save offset
        last_offsets[partition] = message.offset
    
    ok = False
    if tr_type == 'sub':
        print(f"now trying to decrement stock at if loop at line 80")
        sql_statement = """UPDATE stock SET stock = stock - %s WHERE item_id = %s AND stock >= %s;"""
        try:
            for item in items:
                print(f"now attempting to update the stock database: ")
                id, amnt = item['id'], item['amnt']
                cursor.execute(sql_statement, (amnt, id, amnt))
                if cursor.rowcount == 0:
                    connector.rollback()
                    # TODO: set ok to false here?
                    raise Exception("Couldn't subtract enough stock")
            
            ok = True
        except:
            print("failed to decrement stock")
            print(f"try block failed and ok variable should be false but it is ok = {ok}")
            # TODO: SET ok to false here?
            connector.rollback()
    
    else:
        print(f"now trying to increase stock at if loop at line 100")
        sql_statement = """UPDATE stock SET stock = stock + %s WHERE item_id = %s;"""
        for item in items:
            id, amnt = item['id'], item['amnt']
            cursor.execute(sql_statement, (amnt, id))
        #TODO there is no roll back here, there is no try catch block here
    
    try: 
        sql_statement2 = """INSERT INTO messages(order_id, transaction_number, sign)
                                VALUES (%s, %s, %s);"""
        print(f'the value of the inserted values are order_id : {order_id}, tr_num: {tr_num}, tr_type -> sign : {tr_type}')
        print(f'the type of the inserted values are order_id : {type(order_id)}, tr_num: {type(tr_num)}, tr_type -> sign : {type(tr_type)}')
        cursor.execute(sql_statement2, (int(order_id), tr_num, tr_type)) 
        connector.commit()
    except Exception as err:
        print(err)
        connector.rollback()

    if not isinstance(tr_num, int):
        raise Exception(f"tr_num is not an int instead it is of this type: {type(tr_num)}")
    
    if not isinstance(order_id, str):
        raise Exception(f"order_id is not an int instead it is of this type: {type(order_id)}")    

    if ok and tr_type == 'sub':
        producer.send(
            'Outcomes-topic',
            key = {
                'order_id': order_id,
                'tr_num': tr_num
            },
            value = {
                'type': 'ssucc',
                'type': tr_type,
                'items': items
            }
        )
        print(f"stock consumer has sent a message: at line 117 to Outcomes-topic the key is = {{'order_id': {order_id},'tr_num': {tr_num}}} and the value is = {{'type': 'ssucc','type': {tr_type},'items': {items}}} ")
    elif tr_type == 'sub':
        producer.send(
            'Outcomes-topic',
            key = {
                'order_id': order_id,
                'tr_num': tr_num
            },
            value = {
                'type': 'sfail',
                'type': tr_type,
                'items': items
            }
        )
        print(f"stock consumer has sent a message: at line 117 to Outcomes-topic the key is = {{'order_id': {order_id},'tr_num': {tr_num}}} and the value is = {{'type': 'ssucc','type': {tr_type},'items': {items}}} ")