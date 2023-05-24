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
    group_id = 'stock_consumer',
    value_deserializer=lambda v: json.loads(v.decode('ascii')),
    key_deserializer=lambda v: json.loads(v.decode('ascii')),
    auto_offset_reset='earliest',
)

opsConsumer.subscribe(topics=['outcomes'])

############################################ Deal with messages functions
############################################

# Changes the message's partition state when needed, by adding message 
# to pending messages or tr_id = (order_id, tr_num) to done transactions
def addMessageToState(message, partitionsState: dict):
    partDict = partitionsState[message.partition]
    pending = partDict['tr_pending']
    tr_id = (message.key['order_id'], message.key['tr_num'])

    # I don't need to add the transaction done message to the pending messages, at most add tr_id to done transactions
    if message.value['type'] in ['trsucc', 'trfail'] and tr_id in pending.keys():
        partDict['tr_done'].add(tr_id)
    else:
        # if this is the first message from this transaction
        if tr_id not in pending.keys():
            pending[tr_id] = []
            partDict['tr_start_offset'].append(tr_id, message.offset)
            
        pending[tr_id].append(message)

# Takes as input the two messages 
def sendOutcomeMessages(pending: list):
    if len(pending) != 2:
        return
    m1, m2 = pending
    
    # If for some reason we have 2 message from stock or 2 messages from pay:
    # m1.value['type'][0] = first letter, 'p' or 's' 
    if m1.value['type'][0] == m2.value['type'][0]:
        pending.pop(1)
        return
    
    # If both operation succeded:
    if m1.value['type'][1:] == m2.value['type'][1:] == 'succ':
        producer.send(
            'outcomes',
            key = m1.key,
            value = {
                'type': 'trsucc'
            }
        )
        return

    producer.send(
        'outcomes',
        key = m1.key,
        value = {
            'type': 'trfail'
        }
    )

    # If both have failed there is no need to send rollbacks
    if m1.value['type'][1:] == m2.value['type'][1:] == 'fail':
        return
    
    nonFailed = m2
    if m2.value['type'][1:] == 'fail':
        nonFailed = m1
    
    match nonFailed.value['type'][0]:
        case 'p': type, topic = 'can', 'pay'
        case 's': type, topic = 'add', 'stock'

    value = nonFailed.value.copy()
    value['type'] = type
    
    producer.send(
        topic = topic,
        key= nonFailed.key,
        value = value
    )


def getCommittedOffsets(partitionNumber: int):
    
    consumer = KafkaConsumer(
        # boostrap_servers = ?,
        value_deserializer=lambda v: json.loads(v.decode('ascii')),
        key_deserializer=lambda v: json.loads(v.decode('ascii'))
    )

    topicPartition = TopicPartition('outc_offs', partitionNumber)
    
    end_offsets = consumer.end_offsets([topicPartition])

    offset = end_offsets[topicPartition]
    if offset == 0:
        return 0
    
    consumer.assign([partition])
    consumer.seek(partition, offset - 1)
    
    return next(consumer).value['offset']

# 
def buildState(partitionsState: dict, partitionNumber: int, currentOffset: int):

    if partitionNumber not in partitionsState.keys():
        partitionsState[partitionNumber] = {
            'offset_to_read' : getCommittedOffsets(partitionNumber),
            'tr_start_offset': deque(),  # holds ((order_id, tr_num), offs of first message)
            'tr_pending': {},   # for (order_id, tr_num) holds list of msgs
            'tr_done': set()    # holds (order_id, tr_num) of ended transactions,
                                # needed for lazy removal of transactions in tr_start_offset
        }
    
    partDict = partitionsState[partitionNumber]
    consumer = KafkaConsumer(
        # boostrap_servers = ?,
        value_deserializer=lambda v: json.loads(v.decode('ascii')),
        key_deserializer=lambda v: json.loads(v.decode('ascii'))
    )

    partition = TopicPartition('outcomes', partitionNumber)
    consumer.assign([partition])
    consumer.seek(partition, partDict['offset_to_read'])
    
    # TODO: check if makes sense
    partDict['offset_to_read'] = currentOffset

    for msg in consumer:
        
        # > just in the case that asynch commit did not commit the offsets of read messages 
        # before the consumer died, but after the consumer pushed an offset to outc_offs
        if msg.offset >= currentOffset:
            partDict['offset_to_read'] = msg.offset
            break
        
        addMessageToState(msg, partitionsState)
    
    
    # if there is no new offset to push to outc_offs
    if len(partDict['tr_start_offset']) == 0: return

    commitOffset = None
    while(partDict['tr_start_offset'][0] in partDict['tr_done']):
        partDict['tr_done'].remove(partDict['tr_start_offset'][0] )
        partDict['tr_start_offset'].popleft()
        
        if len(partDict['tr_start_offset']) > 0:
            commitOffset = partDict['tr_start_offset'][1]
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
            'outc_offs',
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
    if partition not in partitionsStates.keys() or partitionsStates[partition]['offset_to_read']!=offset:
        buildState(partitionsStates, partition, offset)
        opsConsumer.seek(partition, partitionsStates[partition]['offset_to_read'])

    partState = partitionsStates[partition]
    addMessageToState(message, partitionsStates)
    sendOutcomeMessages(partState['pending'][tr_key])
    partState['offset_to_read'] += 1
