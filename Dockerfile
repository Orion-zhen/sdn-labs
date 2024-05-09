FROM ubuntu:20.04
LABEL maintainer="Orion-zhen"
RUN apt update
RUN apt install -y python3 python3-pip python-is-python3 vim
COPY ./ /work/
RUN pip3 install -r /work/requirements.txt
RUN cd /work/ryu-xjtu && python3 setup.py install
EXPOSE 6633 8080
WORKDIR /work