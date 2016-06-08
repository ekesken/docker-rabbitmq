#!/usr/bin/env python
import logging
import os
import subprocess
import time
import socket
import requests


LOGGER = logging.getLogger(__name__)
APP_ID = os.getenv('MARATHON_APP_ID')
MESOS_TASK_ID = os.getenv('MESOS_TASK_ID')
MARATHON_URI = os.environ.get('MARATHON_URI', 'http://marathon.mesos:8080')
HOST_IP = os.getenv('HOST', '127.0.0.1')
HOST_NAME = os.getenv('HOSTNAME')  # docker container_id


def get_marathon_app(app_id):
    response = requests.get('%s/v2/apps%s' % (MARATHON_URI, app_id))
    state = response.json()
    return state['app']


def get_marathon_tasks(app_id):
    response = requests.get('%s/v2/apps%s/tasks' % (MARATHON_URI, app_id))
    state = response.json()
    return state['tasks']


def get_node_ips():
    my_ip = ''
    other_ips = []
    if MARATHON_URI:
        LOGGER.info('Discovering configuration from %s for app %s', MARATHON_URI, APP_ID)
        tasks = get_marathon_tasks(APP_ID)
        LOGGER.info('Found %d tasks for %s', len(tasks), APP_ID)
        for task in tasks:
            if task['startedAt']:
                node_ip = task['host']
                # for private ips like in calico network, use ip per task
                # see https://mesosphere.github.io/marathon/docs/ip-per-task.html
                if 'ipAddresses' in task:
                    if len(task['ipAddresses']) > 0:
                        node_ip = task['ipAddresses'][0]['ipAddress']
                        LOGGER.info('Task ip is %s, slave ip is %s', node_ip, task['host'])

                LOGGER.info('Found started task %s at %s', task['id'], node_ip)
                if task['id'] == MESOS_TASK_ID:
                    LOGGER.info('My own ip/hostname is %s', my_ip)
                    my_ip = node_ip
                else:
                    other_ips.append(node_ip)
    return my_ip, other_ips


def wait_for_nodes_to_start():
    while True:
        current_app = get_marathon_app(APP_ID)
        configured_count = current_app['instances']
        running_count = current_app['tasksRunning']
        if running_count == configured_count:
            break
        LOGGER.info('%s is configured to have %d tasks,'
                    ' there are %d running tasks now,'
                    ' waiting for one minute...',
                    APP_ID, configured_count, running_count)
        time.sleep(60)
    LOGGER.info('%s has %d running tasks now', APP_ID, running_count)


def is_ip(ip):
    try:
        socket.inet_aton(ip)
        return True
    except socket.eror:
        return False


def get_node_name(node_ip):
    node_name = node_ip
    if is_ip(node_ip):
        node_name = node_ip.replace('.', '-')
    return node_name


def configure_name_resolving(current_node_ip, other_node_ips=None):
    LOGGER.info('Adding extra entries to /etc/hosts...')
    current_node_hostname = get_node_name(current_node_ip)
    with open('/etc/hosts', 'a') as f:
        LOGGER.info('Adding current node entries...')
        host_name_entry = '127.0.0.1 %s' % HOST_NAME
        f.write(host_name_entry + '\n')
        LOGGER.info('+' + host_name_entry)
        current_host_entry = '127.0.0.1 %s' % current_node_hostname
        f.write(current_host_entry + '\n')
        LOGGER.info('+' + current_host_entry)
        if other_node_ips:
            LOGGER.info('Adding other node entries...')
            for node_ip in other_node_ips:
                if node_ip != current_node_ip:
                    if not is_ip(node_ip):
                        # if mesos slaves using hostname instead of ip
                        # no need to add anything to /etc/hosts
                        # docker container is expected to resolve
                        # mesos-slave hostnames already.
                        LOGGER.info('Skipping %s, not an ip', node_ip)
                        continue
                    node_hostname = get_node_name(node_ip)
                    node_host_entry = '%s %s' % (node_ip, node_hostname)
                    f.write(node_host_entry + '\n')
                    LOGGER.info('+' + node_host_entry)
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
            nodes_str = ','.join(["'rabbit@%s'" % get_node_name(n)
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
    wait_for_nodes_to_start()
    my_ip, other_ips = get_node_ips()
    current_node_hostname = configure_name_resolving(my_ip, other_ips)
    configure_rabbitmq(current_node_hostname, other_ips)
    subprocess.call(['rabbitmq-server'])


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    run()
