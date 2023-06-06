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

Nicky Ju

# Issues that arose