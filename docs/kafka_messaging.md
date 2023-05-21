# Topics

## Pay
#### Description:
It will hold all messages needed to checkout or rollback a transaction pay

#### Producers:
- order/checkout: produces initial checkout payment statement
- order consumer: produces a rollback-increment statement (when needed)

#### Consumers:
- pay consumer: deals with committing changes in durable storage

## Stock
#### Description:
It will hold all messages needed decrement or increment all quantities needed for a transaction. Per transaction there are at most two messages:
    - one to decrement quantities for all items in an order
    - the compensation message to increment quantities for all items in an order

#### Producers:
- order/checkout: produces initial checkout decrement statement
- order consumer: produces a rollback-increment statement (when needed)

#### Consumers:
- stock consumer

## Outcome P&S
#### Description:
It holds success or failure messages produced by pay consumer and stock consumer relative to their changes in db

#### Producers:
- pay consumer
- stock consumer

#### Consumers:
- order consumer

## Outcome checkout
#### Description:
It holds messages relative to the success or failure of transactions as a whole

#### Producers:
- order consumer

#### Consumers:
- order/checkout


## Pay offsets
#### Description:
Per partition it holds the offset of the last fully processed message
#### Producers:
- pay consumer
#### Consumers:
- pay consumer (when initializing, needed for fault recovery)

## Stock offsets
#### Description:
Per partition it holds the offset of the last fully processed message
#### Producers:
- stock consumer
#### Consumers:
- stock consumer (when initializing, needed for fault recovery)

## Outcome P&S
#### Description:
Per partition it holds the offset of the start of the oldest transaction not fully processed
#### Producers:
- order consumer
#### Consumers:
- order consumer (when initializing, needed for fault recovery)