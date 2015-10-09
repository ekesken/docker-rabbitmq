#!/usr/bin/env python

import os
import subprocess
import time
import urllib3
import json


APP_ID = os.getenv('MARATHON_APP_ID')

# add extra entry for hosts
host = os.getenv('HOST')
if not host:
    host = '127.0.0.1'

current_host = host.replace('.', '-')
with open('/etc/hosts', 'a') as file:
    file.write('127.0.0.1 %s\n' % os.getenv('HOSTNAME'))
    file.write('127.0.0.1 %s\n' % current_host)
os.putenv('HOSTNAME', current_host)

with open('/etc/rabbitmq/rabbitmq-env.conf', 'a') as file:
    file.write('NODENAME=rabbit@%s\n' % current_host)

def get_marathon_tasks(app_id):
    http = urllib3.PoolManager()
    response = http.request('GET', 'http://leader.mesos:8080/v2/apps%s/tasks' % app_id)
    state = json.loads(response.data)
    return state['tasks']

# start rabbit
print "Starting cluster"
endpoint = 'leader.mesos:8080'
peers = []
if endpoint:
   print 'Discovering configuration from %s for app %s' % (endpoint, APP_ID)
   tasks = get_marathon_tasks(APP_ID)
   print 'Found %d tasks for %s' % (len(tasks), APP_ID)
   for task in tasks:
       if task['startedAt'] and task['host'] != host:
           peers.append(task['host'])

cluster = None
if len(peers) > 0:
    cluster = peers[0]
    print 'Found cluster %s' % cluster

if not cluster:
    subprocess.call(['service', 'rabbitmq-server', 'start'])
else:
    # set entry in hosts for the cluster
    current_cluster = cluster.replace('.', '-')
    with open('/etc/hosts', 'a') as file:
        file.write('%s %s\n' % (cluster, current_cluster))

    subprocess.call(['service', 'rabbitmq-server', 'start'])
    time.sleep(10)
    subprocess.call(['rabbitmqctl', 'stop_app'])
    subprocess.call(['rabbitmqctl', 'reset'])
    subprocess.call(['rabbitmqctl', 'join_cluster', 'rabbit@%s' % current_cluster])
    subprocess.call(['rabbitmqctl', 'start_app'])
    time.sleep(10)

# sleep forever
while True:
    time.sleep(1)
