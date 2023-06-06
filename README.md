# Web-scale Data Management Project

Click here to see our group's [declaration of honour](DeclarationOfHonour.md).

###
To deploy the services in a kuberneters cluster using minikube, follow the instructions in the [`deploy-charts-and-start-minikube.sh`](deploy-charts-and-start-minikube.sh) file.

# todo: Add link to kafka documentation and add a the drawio image s png to readme
# todo add instructions for minikube delete

### Project design
Implementation of a checkout system that follows the design pattern SAGA's and is idempotent, ensuring that some operations should achieve the same result each time regardless of the number of times the operation is carried out.
The project uses Apache Kafka to guarantee eventual consistency for checking out items. Apache Kafka helps to handle data streams, its scalable, fault tolerant and a durable messaging system. Furthermore, we use Redis as a cache 
to store the price of items after the price is requested from the stock service. 

### Project structure

* [`env`](env)
    Folder containing the Redis and PostgreSQL env variables used for the docker-compose deployment (not used for the minikube deployment)
    
* [`helm-config`](helm-config) 
   Helm chart values for:
   - [Redis database](helm-config/redis-helm-values.yaml) (used by order service to store prices)
   - [kafka broker servers](helm-config/kafka.yaml)
   - [PostgreSQL database for order service](helm-config/order-db.yaml)
   - [PostgreSQL database for payment service](helm-config/payment-db.yaml)
   - [PostgreSQL database for stock service](helm-config/stock-db.yaml)
        
* [`k8s`](k8s)
    Folder containing the kubernetes deployments, apps and services for the [ingress](k8s/ingress-service.yaml), [order](k8s/order-app.yaml), [payment](k8s/user-app.yaml) and [stock](k8s/stock-app.yaml) services. Moreover, the consumers of each of the three services are also found here.
    
* [`order`](order)
    Folder containing the order application logic for the [order app](order/app.py) which handles the api requests and the [order consumer](order/consumer.py) which produces and consumes kafka messages when orders are checked out. The dockerfile is also found here (used in minikube deployment). There is also an order_db subfolder here, which is used for setting up and configuring the order_db for local docker development (not used for k8s deployment). 
    
* [`payment`](payment)
    Folder containing the order application logic for the [payment app](payment/app.py) which handles the api requests and the [payment consumer](payment/consumer.py) which produces and consumes kafka messages when the credit balance of users are decreased or rolled back. The dockerfile is also found here (used in minikube deployment). There is also an payment_db subfolder here, which is used for setting up and configuring the payment_db for local docker development (not used for k8s deployment).

* [`stock`](stock)
    Folder containing the order application logic for the [stock app](stock/app.py) which handles the api requests and the [stock consumer](stock/consumer.py) which produces and consumes kafka messages when the stock of an item is decreased or rolled back. The dockerfile is also found here (used in minikube deployment). There is also an stock_db subfolder here, which is used for setting up and configuring the stock_db for local docker development (not used for k8s deployment).
* [`test`](test)
    * [test-microservices](test/test-microservices/) From the project template we have received this folder containing some basic correctness tests for the entire system. (Feel free to enhance them). Because we had difficulty with deploying kafka in docker, but managed in minikube, we have decided to turn the provided python test scripts into a docker image which is then used by [test-microservices.yaml](test/test-microservices/test-microservice.yaml) to test for consistency. To run this test use the kubectl apply command to apply test-microservices.yaml to the cluster. You might need to replace the value of the `URL` environment variable (at line 22) in this file depending on the ip address that the deployed ingress (AKA API gateway). You can find correct value by running `kubectl get ingress`, in the output you should find the ip address under the column [todo]. [todo, tell reader to check the corresponding log of this pod to inspect whether the test has passed or not]
    * [stress-test-k8s](test/stress-test-k8s/) This folder contains the code provided by [the benchmark repository](https://github.com/delftdata/wdm-project-benchmark). The script from that repository did not work for us out of the box. To make it work for us, we had to make the following modification to [run.sh](test/stress-test-k8s/docker-image/locust-tasks/run.sh) (had to fix there were issues with the constructed command) and [tasks.py](test/stress-test-k8s/docker-image/locust-tasks/tasks.py). A docker image was created from these scripts and pushed to a public docker registry, this image is the used by the 3 kubenetes yaml files in the [kubernetes-config file](test/stress-test-k8s/kubernetes-config/). [todo tell reader to first deploy microservices and ingress and consumers and dbs and kafka etc + check if the ip adress is correct] After deploying you can visit locust UI at [localhost:8089](http://localhost:8089) to start the locust script.
    * [consistency](test/consistency/) From the consistency test of [the benchmark repository](https://github.com/delftdata/wdm-project-benchmark), we made a kubernetes deployment which runs those test. To run this test in minikube, apply the [consistency.yaml](test/consistency/consistency.yaml) file to the cluster using the `kubectl apply` command. Inspect the results by checking the logs of the corresponding pod: kubectl get pods to copy the name of the pod from the column (podname+....) then kubectl logs <paste the pod name you copied>. Just like the other steps make sure that the ip address is the same as the ip of you ingress


### Deployment types:

#### docker-compose (local development)

After coding the REST endpoint logic run `docker-compose up --build` in the base folder to test if your logic is correct
(you can use the provided tests in the `\test` folder and change them as you wish). 

***Requirements:*** You need to have docker and docker-compose installed on your machine.

#### minikube (local k8s cluster)

This setup is for local k8s testing to see if your k8s config works before deploying to the cloud. 
First deploy your database using helm by running the `deploy-charts-minicube.sh` file (in this example the DB is Redis 
but you can find any database you want in https://artifacthub.io/ and adapt the script). Then adapt the k8s configuration files in the
`\k8s` folder to mach your system and then run `kubectl apply -f .` in the k8s folder. 

***Requirements:*** You need to have minikube (with ingress enabled) and helm installed on your machine.

#### kubernetes cluster (managed k8s cluster in the cloud)

Similarly to the `minikube` deployment but run the `deploy-charts-cluster.sh` in the helm step to also install an ingress to the cluster. 

***Requirements:*** You need to have access to kubectl of a k8s cluster.
