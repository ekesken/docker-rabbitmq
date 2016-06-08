# docker-rabbitmq
docker image to deploy rabbitmq cluster on mesos with one marathon app.

Marathon config example:

```
{
  "cpus": 1,
  "mem": 1000,
  "id": "test-rabbitmq",
  "instances": 2,
  "constraints": [
    ["hostname", "UNIQUE"],
    ["test-rabbitmq-host", "CLUSTER", "true"]
  ],
  "env": {
    "RABBITMQ_ERLANG_COOKIE": "my_secret_erlrang_cookie",
    "RABBITMQ_DEFAULT_USER": "admin",
    "RABBITMQ_DEFAULT_PASS": "my_secret_pass"
  },
  "container": {
    "type": "DOCKER",
    "docker": {
      "image": "ekesken/rabbitmq",
      "forcePullImage": true,
      "network": "HOST",
      "privileged": true,
    },
    "volumes": [
      {
        "containerPath": "/var/lib/rabbitmq",
        "hostPath": "/var/lib/rabbitmq",
        "mode": "RW"
      }
    ]
  },
  "healthChecks": [
    {
      "protocol": "TCP",
      "gracePeriodSeconds": 600
    }
  ],
  "upgradeStrategy": {
    "minimumHealthCapacity": 0,
    "maximumOverCapacity": 0
  }
}

```

## Calico Networks

Calica network example settings:

```
  ...
  "container": {
    "type": "DOCKER",
    "docker": {
      "image": "ekesken/rabbitmq",
      "forcePullImage": true,
      "parameters": [
        {"key": "net", "value": "calico-net1"}
       ]
    }
  },
  "ipAddress": {"discovery": {"ports": [
    { "number": 5672, "name": "rabbitmq-node-port", "protocol": "tcp"},
    { "number": 15672, "name": "rabbitmq-management-port", "protocol": "tcp"}
  ]}},
```
