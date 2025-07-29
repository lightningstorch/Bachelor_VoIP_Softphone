#!/bin/sh
# short script to wait for RabbitMQ to be ready
# if we don't wait, the app will fail to start and raise an exception because
# the connection to RabbitMQ will not be established
echo "Waiting for RabbitMQ..."
while ! nc -z rabbitmq 5672; do
  sleep 1
done
echo "RabbitMQ is online, starting App"
exec python /app/src/main.py
