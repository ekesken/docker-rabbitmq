FROM rabbitmq:3.5-management

ENV CLUSTER_NODES="'rabbit@localhost'" \
  NODE_NAME='rabbit@localhost'

COPY env-entrypoint.sh /env-entrypoint.sh
RUN chmod +x /env-entrypoint.sh

ENTRYPOINT ["/env-entrypoint.sh"]
