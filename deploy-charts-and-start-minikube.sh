#!/usr/bin/env bash

# make sure to have the latest images locally
docker-compose build

# start minikube and apply the deployment and ingresses
minikube start

# If not already enabled, add the ingress
minikube addons enable ingress

# set up the postgres db before the 3 service, or else they wont connect to the db
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm install my-postgresql -f helm-config/postgresql-helm-values.yaml bitnami/postgresql

# move images to minikube virtual machine
minikube image load order:latest
minikube image load stock:latest
minikube image load user:latest


cd k8s
kubectl apply -f .
cd ..
minikube tunnel

# Ctrl + C to stop the tunnel
# when done clean up to free resources
# helm uninstall my-postgresql
# cd k8s
# kubectl delete -f .