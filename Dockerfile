FROM python:3-alpine

COPY requirements.txt /

RUN apk --update add --virtual build-dependencies build-base libffi-dev tzdata \
  && cp /usr/share/zoneinfo/Etc/UTC /etc/localtime \
  && pip install -r /requirements.txt \
  && apk del build-dependencies build-base libffi-dev tzdata \
  && rm -fR /root/.cache

WORKDIR /tmp/x
COPY laporte/*py ./laporte/
COPY laporte/templates/*html ./laporte/templates/
COPY laporte/static/js/*js ./laporte/static/js/
COPY setup.py README.md MANIFEST.in LICENSE requirements.txt ./
RUN  pip install . 

WORKDIR /laporte
COPY conf/* ./conf/

ENTRYPOINT [ "laporte" ]
