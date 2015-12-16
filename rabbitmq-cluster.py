#!/usr/bin/env python
import logging
import os
import subprocess
import time
import urllib3
import json


LOGGER = logging.getLogger(__name__)
APP_ID = os.getenv('MARATHON_APP_ID')
MARATHON_URI = os.environ.get('MARATHON_URI', 'http://leader.mesos:8080')
HOST_IP = os.getenv('HOST', '127.0.0.1')
HOST_NAME = os.getenv('HOSTNAME')  # docker container_id


def get_marathon_tasks(app_id):
    http = urllib3.PoolManager()
    response = http.request('GET', '%s/v2/apps%s/tasks' % (MARATHON_URI, app_id))
    state = json.loads(response.data)
    return state['tasks']


def get_cluster_node_ips():
    node_ips = []
    if MARATHON_URI:
        LOGGER.info('Discovering configuration from %s for app %s', MARATHON_URI, APP_ID)
        tasks = get_marathon_tasks(APP_ID)
        LOGGER.info('Found %d tasks for %s', len(tasks), APP_ID)
        for task in tasks:
            if task['startedAt'] and task['host'] != HOST_IP:
                node_ips.append(task['host'])
    return node_ips


def get_cluster_master_node_ip(node_ips):
    master_node_ip = None
    if len(node_ips) > 0:
        master_node_ip = node_ips[0]
        LOGGER.info('Found master node %s' % master_node_ip)
    return master_node_ip


def configure_name_resolving(node_ips=None):
    LOGGER.info('Adding extra entries to /etc/hosts...')
    current_node_ip = HOST_IP
    current_node_hostname = current_node_ip.replace('.', '-')
    with open('/etc/hosts', 'a') as f:
        LOGGER.info('Adding current node entries')
        host_name_entry = '127.0.0.1 %s' % HOST_NAME
        f.write(host_name_entry + '\n')
        LOGGER.info('+' + host_name_entry)
        current_host_entry = '127.0.0.1 %s' % current_node_hostname
        f.write(current_host_entry + '\n')
        LOGGER.info('+' + current_host_entry)
        if node_ips:
            LOGGER.info('Adding other node entries')
            for node_ip in node_ips:
                if node_ip != current_node_ip:
                    node_hostname = node_ip.replace('.', '-')
                    node_host_entry = '%s %s' % (node_ip, node_hostname)
                    f.write(node_host_entry + '\n')
                    LOGGER.info('+%s' + node_host_entry)
    LOGGER.info('Changing hostname as %s...', current_node_hostname)
    os.putenv('HOSTNAME', current_node_hostname)
    return current_node_hostname


def set_erlang_cookie():
    cookie_file = '/var/lib/rabbitmq/.erlang.cookie'
    rabbitmq_erlang_cookie = os.getenv('RABBITMQ_ERLANG_COOKIE', None)
    existing_rabbitmq_erlang_cookie = None
    cookie_file_exists = os.path.isfile(cookie_file)
    if cookie_file_exists:
        LOGGER.info('Found %s', cookie_file)
        with open(cookie_file, 'r') as f:
            existing_rabbitmq_erlang_cookie = f.read().strip()
            LOGGER.info('Existing erlang cookie is %s', existing_rabbitmq_erlang_cookie)

    if not rabbitmq_erlang_cookie and not existing_rabbitmq_erlang_cookie:
        raise RuntimeError('No erlang cookie is set!')

    if existing_rabbitmq_erlang_cookie\
            and existing_rabbitmq_erlang_cookie != rabbitmq_erlang_cookie:
        LOGGER.warn('%s file contents [%s] do not match RABBITMQ_ERLANG_COOKIE [%s],'
                    ' keeping existing one.',
                    cookie_file, existing_rabbitmq_erlang_cookie, rabbitmq_erlang_cookie)

    if not existing_rabbitmq_erlang_cookie:
        LOGGER.info('Creating erlang cookie file with secret "%s"', rabbitmq_erlang_cookie)
        with open(cookie_file, 'w') as f:
            f.write(rabbitmq_erlang_cookie)
        subprocess.call(['chown', 'rabbitmq', cookie_file])
        subprocess.call(['chmod', '600', cookie_file])


def create_rabbitmq_config_file(node_ips=None):
    rabbitmq_config_file = '/etc/rabbitmq/rabbitmq.config'
    LOGGER.info('Creating %s', rabbitmq_config_file)
    default_user = os.getenv('RABBITMQ_DEFAULT_USER', 'guest')
    default_pass = os.getenv('RABBITMQ_DEFAULT_PASS', 'guest')
    default_vhost = os.getenv('RABBITMQ_DEFAULT_VHOST', '/')
    rabbitmq_management_port = os.getenv('RABBITMQ_MANAGEMENT_PORT', '/')
    with open(rabbitmq_config_file, 'w') as f:
        f.write('[\n')
        f.write('  {rabbit,\n')
        f.write('    [\n')
        f.write('     {loopback_users, []},\n')
        f.write('     {heartbeat, 580},\n')
        f.write('     {default_user, <<"%s">>},\n' % default_user)
        f.write('     {default_pass, <<"%s">>},\n' % default_pass)
        f.write('     {default_vhost, <<"%s">>},\n' % default_vhost)
        f.write('     {cluster_nodes, {[\n')
        if node_ips:
            nodes_str = ','.join(["'rabbit@%s'" % n.replace('.', '-')
                                  for n in node_ips])
            f.write('      %s\n' % nodes_str)
        f.write('      ], disc}}\n')
        f.write('    ]\n')
        f.write('  },\n')
        f.write('  {rabbitmq_management, [{listener, [{port, %s}]}]}\n'
                % rabbitmq_management_port)
        f.write('].\n')


def configure_rabbitmq(current_node_hostname, node_ips):
    with open('/etc/rabbitmq/rabbitmq-env.conf', 'a') as f:
        f.write('NODENAME=rabbit@%s\n' % current_node_hostname)
    # other settings are already in environment like port settings, see Dockerfile
    subprocess.call(['chown', '-R', 'rabbitmq', '/var/lib/rabbitmq'])
    set_erlang_cookie()
    create_rabbitmq_config_file(node_ips)


def run():
    node_ips = get_cluster_node_ips()
    current_node_hostname = configure_name_resolving(node_ips)
    configure_rabbitmq(current_node_hostname, node_ips)
    master_node_ip = get_cluster_master_node_ip(node_ips)
    if not master_node_ip:
        LOGGER.info("There is no other node, running as master node...")
    else:
        LOGGER.info("Master node %s detected, connecting to master...", master_node_ip)
    subprocess.call(['rabbitmq-server'])


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    run()
