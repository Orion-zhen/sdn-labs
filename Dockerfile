FROM debian:11
LABEL maintainer="Orion-zhen"
RUN apt update
RUN apt install -y python3 python3-pip vim
COPY ./ /work/
RUN cd /work/ryu-xjtu && pip install .
RUN pip install networkx
EXPOSE 6633 8080
WORKDIR /work