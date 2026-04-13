FROM registry.rp-wow.ru/trinity-build:latest

RUN mkdir /trinitycore-build && cd /trinitycore-build \
  && cmake /trinitycore-source \
  && make -j2 \
  && make install \
  && rm -rf /trinitycore-build
WORKDIR /usr/local/bin
ENTRYPOINT ["/bin/sh"]
