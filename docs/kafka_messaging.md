# Topics

## Pay-topic
#### Description:
It will hold all messages needed to checkout or rollback a transaction pay

#### Producers:
- order/checkout: produces initial checkout payment statement
- order consumer: produces a rollback-increment statement (when needed)

#### Consumers:
- pay consumer: deals with committing changes in durable storage

#### Messages:
- pay (key: {'order_id':int, 'tr_num': int}, value: ('type':'pay', 'amnt':int))
- cancelPayment (key: {'order_id':int, 'tr_num': int}, value: ('type':'can', 'amnt':int))

## Stock-topic
#### Description:
It will hold all messages needed decrement or increment all quantities needed for a transaction. Per transaction there are at most two messages:
    - one to decrement quantities for all items in an order
    - the compensation message to increment quantities for all items in an order

#### Producers:
- order/checkout: produces initial checkout decrement statement
- order consumer: produces a rollback-increment statement (when needed)

#### Consumers:
- stock consumer

#### Messages:
- decrement (key: {'order_id':int, 'tr_num': int}, value: ('type':'sub', 'items' = [{'id':int, 'amnt':int}, ... ]))
- increment (key: {'order_id':int, 'tr_num': int}, value: ('type':'add', 'items' = [{'id':int, 'amnt':int}, ... ]))

## Outcomes-topic
#### Description:
It holds success or failure messages produced by pay consumer and stock consumer relative to their changes in db, as well as messages from order consumer relative to the outcome of a transaction

#### Producers:
- pay consumer
- stock consumer
- order consumer

#### Consumers:
- order consumer
- order/checkout

#### Messages:
- paySuccess    (key: {'order_id':int, 'tr_num': int}, value: (
                        'type': 'psucc',
                        'user_id': user_id,
                        'amnt': amnt))
- payFail       (key: {'order_id':int, 'tr_num': int}, value: (
    'type': 'pfail',
    'tr_type': tr_type,
    'user_id': user_id,
    'amnt': amnt))
- stockSuccess  (key: {'order_id':int, 'tr_num': int}, value: ('type':'ssucc', 'items' = [{'id':int, 'amnt':int}, ... ]))
- stockFail     (key: {'order_id':int, 'tr_num': int}, value: ('type':'sfail', 'items' = [{'id':int, 'amnt':int}, ... ]))
- transaction success (key: {'order_id':int, 'tr_num': int}, value: ('type':'trsucc'))
- transaction success (key: {'order_id':int, 'tr_num': int}, value: ('type':'trfail'))

## Outc-offs-topic
#### Description:
Per partition it holds the offset of the start of the oldest transaction not fully processed. Order consumers have to:
- read messages from **Outcomes**
- process the message and commit to kafka (increment internal offset)
- Keep tract of all the transaction ids and the offset of their first message (an outcome from pay or stock)
- Once the oldest transaction is done (we received both messages from stock and pay)
    - no need to keep track of that transaction any more
    - push to Offset **Outcomes** the next oldest (smallest) offset
- If a transaction that is not the oldest is done: just lose track of it

When first reading a message of a new partition, and after reading old partition after a few messages, consumers have to fetch the latest offset posted in Outc-offs-topic, and read messages until they reach the committed offset in **Outcomes**, **without** processing them, just in order to rebuild the lost state. When latest committed offset is reached, then they have to start processing messages, sending response messages like normal
#### Producers:
- order consumer

#### Consumers:
- order consumer (when initializing, needed for fault recovery)

#### Messages: 
- offset (key: partition#, value: offset)


# Participants

## order/checkout
#### Topics:
- **Stock-topic**: producer
- **Pay-topic**: producer
- **Outcomes**: consumer

## order consumer
#### Topics:
- **Outcomes**: consumer
- **oc**: producer
- **Outc-offs-topic**: producer and consumer

## pay consumer
- **Pay-topic**: consumer
- **Outcomes**: producer

## Stock-topic consumer
- **Stock-topic**: consumer
- **Outcomes**: producer

# Important notes

- **tr#** is the number of times order/checkout is called, we need this to deal with same messages per same order (namely: checkout -> fail -> cheange something in order -> checkout again). This means that the order table has to be changed like this:
    | OrderId | user_id | paid | items | amount | tr# |
    |-|-|-|-|-|-| 

- For better throughput we can set autocommit to true for kafka consumers. This ensures that messages are read at least once in all partitions, but not that they are read exactly once. To deal with this we can insert the orderid_tr# along with the meaning of the message (pay/decrement vs rollback). This means that we need to create the following table in Stock-topic and payment dbs:

    | Orderid | tr# | Was Rollback|
    |-|-|-|
    | 1 | 2 | False |
    | 1 | 2 | True |


    When reading a message, when doing the transaction we can do a conditional insert to the database, and go through on if the key is not already in db. All three attributes have to compose the primary key

