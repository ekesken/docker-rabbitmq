#!/bin/bash

cat <<EOF >/etc/rabbitmq/rabbitmq.config
[
 {rabbit,
  [%%
      {cluster_nodes, {[$CLUSTER_NODES], disc}}
  ]},
 {kernel,
  [%% Sets the net_kernel tick time.
  ]},
 {rabbitmq_management,
  [%% Pre-Load schema definitions from the following JSON file. See
  ]},
 {rabbitmq_management_agent,
  [%% Misc/Advanced Options
  ]},
 {rabbitmq_shovel,
  [{shovels,
    [%% A named shovel worker.
    ]}
  ]},
 {rabbitmq_stomp,
  [%% Network Configuration - the format is generally the same as for the broker
  ]},
 {rabbitmq_mqtt,
  [%% Set the default user name and password. Will be used as the default login
  ]},
 {rabbitmq_amqp1_0,
  [%% Connections that are not authenticated with SASL will connect as this
  ]},
 {rabbitmq_auth_backend_ldap,
  [%%
  ]},
].
EOF

cat <<EOF >/etc/rabbitmq/rabbitmq.config
NODENAME=$NODE_NAME
EOF

/docker-entrypoint.sh $@
