#!/usr/bin/env bash

# make sure to have the latest images locally
docker-compose build

# set up the postgres db before the 3 service, or else they wont connect to the db
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm install my-postgresql -f helm-config/postgresql-helm-values.yaml bitnami/postgresql

# move images to minikube virtual machine
minikube image load order:latest
minikube image load stock:latest
minikube image load user:latest

# start minikube and apply the deployment and inrgresses
minikube start
cd k8s
kubectl apply -f .
cd ..
minikube tunnel
