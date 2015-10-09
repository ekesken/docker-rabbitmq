FROM rabbitmq:3.5-management

RUN apt-get update && apt-get install -y python python-dev python-pip
RUN pip install marathon

ADD ./rabbitmq-cluster.py /rabbitmq-cluster.py

CMD /rabbitmq-cluster.py
