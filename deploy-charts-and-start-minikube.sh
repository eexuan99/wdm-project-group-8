#!/usr/bin/env bash

# set up the postgres db before the 3 service, or else they wont connect to the db
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm install my-postgresql -f helm-config/postgresql-helm-values.yaml bitnami/postgresql

# start minikube and apply the deployment and inrgresses
minikube start
cd k8s
kubectl apply -f .
cd ..
minikube tunnel
