import os
import psycopg2
import json
from collections import deque
from kafka import KafkaConsumer, KafkaProducer, TopicPartition

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
    # boostrap_servers = ?,
    value_serializer = lambda v: json.loads(v.decode('ascii')),
    key_serializer = lambda v: json.loads(v.decode('ascii')),
)

opsConsumer = KafkaConsumer(
    #client_id = get it from k8s?,
    # boostrap_servers = ?,
    group_id = 'order_consumer',
    value_deserializer=lambda v: json.loads(v.decode('ascii')),
    key_deserializer=lambda v: json.loads(v.decode('ascii')),
    auto_offset_reset='earliest',
)

opsConsumer.subscribe(topics=['Outcomes-topic'])


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
    tr_id = (message.key['order_id'], message.key['tr_num'])

    # I don't need to add the transaction done message to the pending messages, at most add tr_id to done transactions
    if message.value['type'] in ['trsucc', 'trfail'] and tr_id in state.tr_pending.keys():
        state.tr_done.add(tr_id)
    else:
        # if this is the first message from this transaction
        if tr_id not in state.tr_pending.keys():
            state.tr_pending[tr_id] = []
            state.tr_start_offset.append(tr_id, message.offset)
            
        state.tr_pending[tr_id].append(message)

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
        sql_statement = """UPDATE order_table SET paid = 'paid' WHERE order_id = %s;"""

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
    sql_statement = """UPDATE order_table SET paid = 'not_paid' WHERE order_id = %s;"""

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


# Fetches the last message from Outc-offs-topic (from specified partition) and returns it
def getCommittedOffset(partitionNumber: int) -> int:
    
    consumer = KafkaConsumer(
        # boostrap_servers = ?,
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
        # boostrap_servers = ?,
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
        
        addMessageToState(msg, partitionsState)
    
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
            # boostrap_servers = ?,
            value_serializer = lambda v: json.loads(v.decode('ascii')),
            key_serializer = lambda v: json.loads(v.decode('ascii')),
        )
        producer.send(
            'Outc-offs-topic',
            value={ 'offset':commitOffset },
            partition=partitionNumber
        )


############################################ Read Message loop ############################################

partitionsStates = {}

for message in opsConsumer:
    tr_key =  message.key
    partition = message.partition
    offset = message.offset
    
    # TODO: check if loops with build state for offset_to_read
    if partition not in partitionsStates.keys() or partitionsStates[partition].offset_to_read!=offset:
        buildState(partitionsStates, partition, offset)
        opsConsumer.seek(partition, partitionsStates[partition].offset_to_read)
        message = opsConsumer.next()

    state = partitionsStates[partition]
    addMessageToState(message, partitionsStates)
    sendOutcomeMessages(state.pending[tr_key])
    state.offset_to_read += 1
