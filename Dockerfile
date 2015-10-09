FROM rabbitmq:3.5-management

RUN apt-get update && apt-get install -y python python-pip

ADD ./rabbitmq-cluster.py /rabbitmq-cluster.py
RUN chmod +x /rabbitmq-cluster.py

ENTRYPOINT ["/rabbitmq-cluster.py"]

