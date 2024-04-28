FROM ubuntu:20.04
LABEL maintainer="Orion-zhen"
RUN apt update && apt install -y python3 python3-pip python-is-python3 vim && pip3 install ryu && pip3 install eventlet==0.30.2 && pip3 install networkx
EXPOSE 6633 8080
WORKDIR /work
COPY ./ /work/