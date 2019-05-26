FROM python:3-alpine

COPY requirements.txt /

RUN apk --update add --virtual build-dependencies build-base tzdata \
  && cp /usr/share/zoneinfo/Etc/UTC /etc/localtime \
  && pip install -r /requirements.txt \
  && apk del build-dependencies tzdata \
  && rm -fR /root/.cache

WORKDIR /switchboard
COPY switchboard.py /switchboard/
COPY sensors/*py /switchboard/sensors/
COPY conf/*yml /switchboard/conf/
COPY templates/*html /switchboard/templates/

ENTRYPOINT [ "python", "switchboard.py" ]

