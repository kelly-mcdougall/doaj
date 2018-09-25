#!/usr/bin/env bash
THIS_SCRIPT=`basename "$0"`
[ $# -ne 1 ] && echo "Call this script as $THIS_SCRIPT <environment: [production, staging, test, harvester]>" && exit 1

ENV=$1
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

# Create directory structure for the redis database
mkdir -p /home/cloo/appdata/doaj
mkdir -p /home/cloo/appdata/doaj/redis

# Install redis from apt
sudo apt-get update -q -y
sudo apt-get -q -y install redis-server=2:2.8.4-2

echo "Configuring redis to use DOAJ config file and run under supervisor"
sudo ln -sf $DIR/redis/redis.conf /etc/redis/redis.conf

echo "Configuring redis to use host $REDIS_BIND_HOST and port $HUEY_REDIS_PORT"
sudo sed -i "s/^port.*$/port $HUEY_REDIS_PORT/g" /etc/redis/redis.conf
sudo sed -i "s/^bind.*$/$REDIS_BIND_HOST/g" /etc/redis/redis.conf

# Restart redis
/home/cloo/repl/$ENV/doaj/src/doaj/deploy/restart-redis.sh $ENV
