FROM python:3-alpine

WORKDIR /tmp/x
COPY setup.py README.md MANIFEST.in LICENSE requirements.txt ./

RUN apk --update add --virtual build-dependencies build-base libffi-dev tzdata \
  && cp /usr/share/zoneinfo/Etc/UTC /etc/localtime \
  && pip install -r requirements.txt \
  && apk del build-dependencies build-base libffi-dev tzdata \
  && rm -fR /root/.cache

COPY laporte/ ./laporte/
RUN  pip install . 

WORKDIR /laporte
COPY conf/* ./conf/

ENTRYPOINT [ "laporte" ]
