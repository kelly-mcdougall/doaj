#!/usr/bin/env bash
THIS_SCRIPT=`basename "$0"`
[ $# -ne 1 ] && echo "Call this script as $THIS_SCRIPT <environment: [production, staging, test, harvester]>" && exit 1

ENV=$1

sudo apt-get update -q -y
sudo apt-get -q -y install redis-server=2:2.8.4-2
echo "Configuring redis to use host $REDIS_BIND_HOST and port $HUEY_REDIS_PORT"
sudo sed -i "s/port 6379/port $HUEY_REDIS_PORT/g" /etc/redis/redis.conf
sudo sed -i "s/bind 127.0.0.1/$REDIS_BIND_HOST/g" /etc/redis/redis.conf

echo "Configuring redis to run under supervisor"
sudo sed -i "s/daemonize.*$/daemonize no/g" /etc/redis/redis.conf

# Restart redis
/home/cloo/repl/$ENV/doaj/src/doaj/deploy/restart-redis.sh $ENV
