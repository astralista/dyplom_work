FROM python:3.11.0-alpine

RUN apk add --no-cache netcat-openbsd

ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/