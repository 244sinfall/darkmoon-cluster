FROM debian:12.6

ENV DEBIAN_FRONTEND=noninteractive

# `Screen` for interactive session
RUN apt-get update && apt-get install -y screen && rm -rf /var/lib/apt/lists/*

# TrinityCore requirements
RUN apt-get update && \
    apt-get install -y lsb-release gnupg wget && \
    wget https://dev.mysql.com/get/mysql-apt-config_0.8.29-1_all.deb -O /tmp/mysql-apt-config_all.deb && \
    dpkg -i /tmp/mysql-apt-config_all.deb
RUN apt-get update && apt-get install -y mysql-server
RUN apt-get install -y git clang cmake make gcc g++ \
    default-libmysqlclient-dev libssl-dev libbz2-dev  \
    libreadline-dev libncurses-dev libboost-all-dev p7zip
RUN update-alternatives --install /usr/bin/cc cc /usr/bin/clang 100
RUN update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang 100

# Common requirements. All image dependencies must be located under build-tools
RUN apt-get update && mkdir /external_deps

#COPY ./external_deps /external_deps

# RabbitMQ
#RUN cd /external_deps && tar -xvzf rabbitmq-c-0.14.0.tar.gz && \
#    cd rabbitmq-c-0.14.0 && mkdir build && cd build && \
#    cmake -DCMAKE_INSTALL_PREFIX=/usr/local .. && \
#    cmake --build . --target install

#RUN cd /external_deps && tar -xvzf SimpleAmqpClient-2.5.1.tar.gz && \
#    cd SimpleAmqpClient-2.5.1 && mkdir build && cd build && \
#    cmake -DCMAKE_INSTALL_PREFIX=/usr/local .. -DENABLE_SSL_SUPPORT=ON && \
#    make install

WORKDIR /trinitycore

ENTRYPOINT [ "/bin/sh" ]
