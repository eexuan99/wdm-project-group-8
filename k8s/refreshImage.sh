kubectl delete -f order-app.yaml
kubectl delete -f order-consumer.yaml
#minikube image ls
minikube image rm order:latest
#minikube image rm order:latest
docker-compose build
minikube image load order:latest
kubectl apply -f .