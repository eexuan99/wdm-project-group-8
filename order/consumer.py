import os
from flask import Flask
import psycopg2
import json
from collections import deque
from kafka import KafkaConsumer, KafkaProducer, TopicPartition

app = Flask("order-consumer")

############################################ Data base set up ############################################

connector = psycopg2.connect(
    host=os.environ['POSTGRES_HOST'],
    database=os.environ['POSTGRES_DB'],
    user=os.environ['POSTGRES_USER'],
    password=os.environ['POSTGRES_PASSWORD'],
    port=os.environ['POSTGRES_PORT'])

cursor = connector.cursor()

print("successfully made a database connector")


############################################ Kafka set up ############################################
# TODO: finish
producer = KafkaProducer(
    bootstrap_servers = 'kafka-1.kafka-headless.default.svc.cluster.local:9092,kafka-0.kafka-headless.default.svc.cluster.local:9092,kafka-2.kafka-headless.default.svc.cluster.local:9092',
            value_serializer = lambda v: json.dumps(v).encode('ascii'),
            key_serializer = lambda v: json.dumps(v).encode('ascii'),
)

print("successfully instantiated a kafka producer")

opsConsumer = KafkaConsumer(
    #client_id = get it from k8s?,
    bootstrap_servers = 'kafka.default.svc.cluster.local:9092',
    group_id = 'order_consumer',
    value_deserializer=lambda v: json.loads(v.decode('ascii')),
    key_deserializer=lambda v: json.loads(v.decode('ascii')),
    auto_offset_reset='earliest',
)

opsConsumer.subscribe(topics=['Outcomes-topic'])

print("successfully made a an opsConsumer in order consumer")

############################################ Partition state class ############################################

class PartitionState():
    def __init__(self, number) -> None:
        self.id = number
        self.offset_to_read  = getCommittedOffset(number)
        self.tr_start_offset = deque()  # holds ((order_id, tr_num), offs of first message)
        self.tr_pending = {}   # for (order_id, tr_num) holds list of msgs
        self.tr_done = set()    # holds (order_id, tr_num) of ended transactions,
                            # needed for lazy removal of transactions in tr_start_offset
         


############################################ Deal with messages functions
############################################

# Changes the message's partition state when needed, by adding message 
# to pending messages or tr_id = (order_id, tr_num) to done transactions
def addMessageToState(message, state: PartitionState):
    print(f'message here is: {message}')
    print(f'message is is an empty dict = {not message}')
    tr_id = (message.key['order_id'], message.key['tr_num'])

    # I don't need to add the transaction done message to the pending messages, at most add tr_id to done transactions
    if message.value['type'] in ['trsucc', 'trfail'] and tr_id in state.tr_pending.keys():
        state.tr_done.add(tr_id)
        print(f'===================================== \n Function: addMessageToState(message, state: PartitionState) \n line 70 \n added tr_id {tr_id} to state.tr_done \n =====================================')
    else:
        # if this is the first message from this transaction
        if tr_id not in state.tr_pending.keys():
            state.tr_pending[tr_id] = []
            state.tr_start_offset.append((tr_id, message.offset))
            print(f'===================================== \n Function: addMessageToState(message, state: PartitionState) \n line 74 \n this is the first message from this transaction with tr_id: {tr_id}, created a list and added the tr_id and offset of this message \n =====================================')    
        state.tr_pending[tr_id].append(message)
        print(f'===================================== \n Function: addMessageToState(message, state: PartitionState) \n line 72 else case \n added this message to tr_pending of the state object \n =====================================')
# Takes as input the list of messages from pending.
# If there are no two suitable messages it return (alters list if 2 duplicate messages)
# If there are two suitable messages it sends messages to Outcomes, and eventually 
# to Pay and Stock, then alters the order db to change the payment status
def sendOutcomeMessages(pending: list):
    if len(pending) != 2:
        return
    m1, m2 = pending
    
    # If for some reason we have 2 message from stock or 2 messages from pay:
    # m1.value['type'][0] = first letter, 'p' or 's' 
    if m1.value['type'][0] == m2.value['type'][0]:
        pending.pop(0)
        return
    
    # If both operation succeded:
    if m1.value['type'][1:] == m2.value['type'][1:] == 'succ':
        producer.send(
            'Outcomes-topic',
            key = m1.key,
            value = {
                'type': 'trsucc'
            }
        )
        print(f"order consumer is sending to this topic = Outcomes-topic, key ={m1.key}, value = {{'type': 'trsucc'}} ")
        sql_statement = """UPDATE order_table SET p_status = 'paid' WHERE order_id = %s;"""

        cursor.execute(sql_statement, (m1.key['order_id'],))
        connector.commit()
        return

    producer.send(
        'Outcomes-topic',
        key = m1.key,
        value = {
            'type': 'trfail'
        }
    )
    print(f"order consumer is sending to this topic = Outcomes-topic, key ={m1.key}, value = {{'type': 'trfail'}} ")
    sql_statement = """UPDATE order_table SET p_status = 'not_paid' WHERE order_id = %s;"""

    cursor.execute(sql_statement, (m1.key['order_id'],))
    connector.commit()

    # If both have failed there is no need to send rollbacks
    if m1.value['type'][1:] == m2.value['type'][1:] == 'fail':
        return
    
    nonFailed = m2
    if m2.value['type'][1:] == 'fail':
        nonFailed = m1
    
    match nonFailed.value['type'][0]:
        case 'p': type, topic = 'can', 'Pay-topic'
        case 's': type, topic = 'add', 'Stock-topic'

    value = nonFailed.value.copy()
    value['type'] = type
    
    producer.send(
        topic = topic,
        key= nonFailed.key,
        value = value
    )
    print(f"order-consumer is sending a message to this topic = {topic}, with this key ={nonFailed.key} and this value = {value} ")


# Fetches the last message from Outc-offs-topic (from specified partition) and returns it
def getCommittedOffset(partitionNumber: int) -> int:
    
    consumer = KafkaConsumer(
        bootstrap_servers = 'kafka.default.svc.cluster.local:9092',
        value_deserializer=lambda v: json.loads(v.decode('ascii')),
        key_deserializer=lambda v: json.loads(v.decode('ascii'))
    )

    topicPartition = TopicPartition('Outc-offs-topic', partitionNumber)
    
    end_offsets = consumer.end_offsets([topicPartition])

    offset = end_offsets[topicPartition]
    if offset == 0:
        return 0
    
    consumer.assign([partition])
    consumer.seek(partition, offset - 1)
    
    return next(consumer).value['offset']

# It builds the state for a new partition or repairs an existing state for an old partition.
# If the partition is new, it adds a new PartitionState to the partitionsState dict. When
# doing so, the last offset for that partition is fetched. From this last offset, or from a 
# previous old starting offset, up until the currentOffset, messages are read and added 
# to state, but sendOutcomeMessages is never called.
# It returns nothing, but the state when returning is such that the message at current 
# offset still has to be read, as it needs to be processed.
def buildState(partitionsState: dict, partitionNumber: int, currentOffset: int):

    if partitionNumber not in partitionsState.keys():
        partitionsState[partitionNumber] = PartitionState(partitionNumber)
    state = partitionsState[partitionNumber]
    
    # consumer needed to read all messages from offset in state up to currentOffset
    consumer = KafkaConsumer(
        bootstrap_servers = 'kafka.default.svc.cluster.local:9092',
        value_deserializer=lambda v: json.loads(v.decode('ascii')),
        key_deserializer=lambda v: json.loads(v.decode('ascii'))
    )

    partition = TopicPartition('Outcomes-topic', partitionNumber)
    consumer.assign([partition])
    consumer.seek(partition, state.offset_to_read)
    
    for msg in consumer:
        
        # > just in the case that asynch commit did not commit the offsets of read messages 
        # before the consumer died, but after the consumer pushed an offset to Outc-offs-topic
        if msg.offset >= currentOffset:
            state.offset_to_read = msg.offset
            break
        
        if not msg:
            print("msg at line 200 is an empty dict, which does not have keys")
        print("calling addMessageToState at line 203")
        addMessageToState(msg, state)
    
    # if there is no new offset to push to Outc-offs-topic
    if len(state.tr_start_offset) == 0: return

    # check whether anything has to be pushed to Outc-offs-topic at all
    commitOffset = None
    while(state.tr_start_offset[0] in state.tr_done):
        state.tr_done.remove(state.tr_start_offset[0] )
        state.tr_start_offset.popleft()
        
        if len(state.tr_start_offset) > 0:
            commitOffset = state.tr_start_offset[0][1]
        else:
            commitOffset = currentOffset
            break

    if commitOffset:
        producer = KafkaProducer(
            bootstrap_servers = 'kafka-1.kafka-headless.default.svc.cluster.local:9092,kafka-0.kafka-headless.default.svc.cluster.local:9092,kafka-2.kafka-headless.default.svc.cluster.local:9092',
            value_serializer = lambda v: json.dumps(v).encode('ascii'),
            key_serializer = lambda v: json.dumps(v).encode('ascii'),
        )
        producer.send(
            'Outc-offs-topic',
            value={ 'offset':commitOffset },
            partition=partitionNumber
        )
        print(f"order consumer has sent a message to outc-offs-topic with this value = {{ 'offset':{commitOffset} }} and partitionnumber = {partitionNumber}")


############################################ Read Message loop ############################################

partitionsStates = {}

for message in opsConsumer:
    tr_key =  message.key
    partition = message.partition
    offset = message.offset
    
    if not message:
        print("message is an empty dictionary at line 240")
        raise Exception("an empty message!!!")
        # continue

    print(f"order consumer now consuming message with the following key= {tr_key}, value = {message.value}")
    
    # TODO: check if loops with build state for offset_to_read
    if partition not in partitionsStates.keys() or partitionsStates[partition].offset_to_read!=offset:
        buildState(partitionsStates, partition, offset)
        topic_partition = TopicPartition(topic='Outcomes-topic', partition=partition)

        print(f'======================== \n this is the message BEFORE calling the poll method \n message is empty = {not message} \n message key = {message.key} \n partition = {message.partition} \n offset = {message.offset} \n message type = {type(message)} \n message = {message} \n ======================================= \n')


        opsConsumer.seek(topic_partition, partitionsStates[partition].offset_to_read)

        print(f'======================== \n this is the message AFTER calling the poll method \n message is empty = {not message} \n message key = {message.key} \n partition = {message.partition} \n offset = {message.offset} \n message type = {type(message)} \n message = {message} \n ======================================= \n')


        # message = opsConsumer.poll(timeout_ms=50, max_records=2)
        # print(f'the poll method returns the following type of thing: {type(message)}')
        # print(f'the poll method returns the following thing: {message}')

        # for tp, record_list in message.items():
        #     for record in record_list:
        #         # Process the record here
        #         print(f'record of message value = {record.value} and key is = {record.key}')
        #         if not record:
        #             print("message is an empty dictionary around line 260")
        #             continue
        #         message = record
        #         print(f'message item is changed in the for loop!')
        #         # continue

        # continue
        # continue # message = opsConsumer.next()

    state = partitionsStates[partition]
    print("calling addMessageToState at line 272")
    print(f"message empty at 272 = {not message}")
    addMessageToState(message, state)
    print("calling sendOutcomeMessages at line 283")
    print(f"message empty at 283 = {not message}")
    sendOutcomeMessages(state.tr_pending[(message.key['order_id'], message.key['tr_num'])])
    state.offset_to_read += 1
