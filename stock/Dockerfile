FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /home/flask-app

COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000