FROM rabbitmq:3.5-management

ENV CLUSTER_NODES="'rabbit@localhost'"

COPY env-entrypoint.sh /env-entrypoint.sh
RUN chmod +x /env-entrypoint.sh

ENTRYPOINT ["/env-entrypoint.sh"]
