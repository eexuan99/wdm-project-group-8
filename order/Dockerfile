FROM python:3.11-slim

WORKDIR /home/flask-app

COPY ./requirements.txt .

RUN apt-get update \
    && apt-get -y install libpq-dev gcc

RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000