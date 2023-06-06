# Who did what 

Bryan He:
- k8s deployment scripts:
    - deployed kafka brokers with the necessary topics and need number of partitions.
    - deployed the apps and kafka consumer of the three services.
    - deployed the locust stress test, consistency test and test-microservices.py in the minikube cluster for testing and benchmarking.
    - deployed the 3 PostgreSQL with the correct schemas and 1 Redis databases. 
- connecting the microservices with the databases using the psycopg2 python module.
- connecting the kafka message consumers with the deployed kafka brokers to enable producing and consuming messages.
- debug the checkout endpoint of the order service and the kafka message consumers of the 3 services.
- helped with writing the prepared SQL statements needed to deal with adding and removing items from orders.

Pierluigi Negro

Ee Xuan Tan
- Worked on the transactional protocol (payment service)
    - Implemented all the requests
- Worked on the addItem and removeItem in the order service 
    - Set up Redis as a cache for the order microservice to save item prices from the stock service
    - Created a request from one service to the other service to retrieve item prices
    - Updated the SQL statements to update total order price and items.
- Looked into setting up Apache Kafka on Docker
- Worked on the presentation

Nicky Ju

# Issues that arose