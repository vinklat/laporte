#!/usr/bin/env python

from gevent import monkey
monkey.patch_all()
from flask import Flask, request, Response, abort, render_template, session
from flask_restful import Resource, Api
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect
from flask_bootstrap import Bootstrap
from gevent.pywsgi import WSGIServer, LoggingLogAdapter
from argparse import ArgumentParser, ArgumentTypeError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from prometheus_client.core import REGISTRY
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import yaml
import json
import logging
from sensors import Sensors

##
## cmd line argument parser
##

parser = ArgumentParser(description='Switchboard')
parser.add_argument(
    '-a',
    '--address',
    action='store',
    dest='addr',
    help='listen address',
    type=str,
    default="")
parser.add_argument(
    '-p',
    '--port',
    action='store',
    dest='port',
    help='listen port',
    type=int,
    default=9128)
parser.add_argument(
    '-c',
    '--sensor-config',
    action='store',
    dest='sensors_fname',
    help='sensor config yaml file',
    type=str,
    default='conf/sensors.yml')

LOG_LEVEL_STRINGS = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']


def log_level_string_to_int(log_level_string):
    if not log_level_string in LOG_LEVEL_STRINGS:
        message = 'invalid choice: {0} (choose from {1})'.format(
            log_level_string, LOG_LEVEL_STRINGS)
        raise ArgumentTypeError(message)

    log_level_int = getattr(logging, log_level_string, logging.INFO)
    # check the logging log_level_choices have not changed from our expected values
    assert isinstance(log_level_int, int)

    return log_level_int


parser.add_argument(
    '-l',
    '--log-level',
    action='store',
    dest='log_level',
    help='set the logging output level. {0}'.format(LOG_LEVEL_STRINGS),
    type=log_level_string_to_int,
    default='INFO')

pars = parser.parse_args()

##
## create logger
##

logger = logging.getLogger('switchboard')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(pars.log_level)
formatter = logging.Formatter('%(levelname)s %(name)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

##
## create application
##

app = Flask(__name__)
api = Api(app)
bootstrap = Bootstrap(app)
sensors = Sensors()
with open(pars.sensors_fname, 'r') as stream:
    try:
        config_dict = yaml.load(stream)
        sensors.add_sensors(config_dict)
    except yaml.YAMLError as exc:
        logger.error(exc)

REGISTRY.register(sensors.CustomCollector(sensors))

##
## Prometheus API
##


class PrometheusMetrics(Resource):
    def get(self):
        return Response(
            generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)


api.add_resource(PrometheusMetrics, '/metrics')

##
## Socket.IO
##

async_mode = 'gevent'
sio = SocketIO(app, async_mode=async_mode)


class SensorsNamespace(Namespace):
    def on_sensor_response(self, message):
        logger.debug('SocketIO: {} '.format(message))
        for node_id in message:
            request_form = message[node_id]
            logger.info('SocketIO in: {}: {}'.format(node_id,
                                                     str(request_form)))
            try:
                sensors.set_values(node_id, request_form)
            except KeyError:
                pass

    def on_join(self, message):
        logger.debug('SocketIO client join: {} '.format(message))
        source = message['room']
        join_room(source)
        emit('status_response', {'joined in': rooms()})
        emit('config_response',
             {source: list(sensors.get_sensors_addr_config(source))})

    def on_connect(self):
        emit('status_response', {'status': 'connected'})

    def on_ping(self):
        emit('pong')


class EventsNamespace(Namespace):
    def on_connect(self):
        emit(
            'event',
            json.dumps(sensors.get_sensors_dict_by_node(skip_None=False)),
            broadcast=True)

    def on_ping(self):
        emit('pong')


sio.on_namespace(SensorsNamespace('/sensors'))
sio.on_namespace(EventsNamespace('/events'))
sensors.sio = sio

##
## REST API methods
##


class Sensor(Resource):
    def put(self, node_id):
        logger.info("API: {}: {}".format(node_id, str(request.form.to_dict())))
        try:
            ret = sensors.set_values(node_id, request.form)
        except KeyError:
            logger.warning("node {} not found".format(node_id))
            abort(404)  #not configured

        return ret


class SensorsSource(Resource):
    def get(self, source):
        try:
            ret = list(sensors.get_sensors_addr_config(source))
        except KeyError:
            logger.warning("source {} not found".format(source))
            abort(404)  #not configured

        return ret


class SensorsDump(Resource):
    def get(self):
        return sensors.get_sensors_dump_list()


class SensorsData(Resource):
    def get(self):
        return list(sensors.get_sensors_data(skip_None=False))


class SensorsDataByNode(Resource):
    def get(self):
        return sensors.get_sensors_dict_by_node()


class SensorsDataBySensor(Resource):
    def get(self):
        return sensors.get_sensors_dict_by_sensor()


api.add_resource(Sensor, '/api/sensor/<string:node_id>')
api.add_resource(SensorsSource, '/api/sensors/source/<string:source>')
api.add_resource(SensorsDump, '/api/sensors/dump')
api.add_resource(SensorsData, '/api/sensors')
api.add_resource(SensorsDataByNode, '/api/sensors/by_node')
api.add_resource(SensorsDataBySensor, '/api/sensors/by_sensor')

##
## Web
##


@app.route('/')
@app.route('/table')
def table():
    return render_template(
        'index.html',
        async_mode=sio.async_mode,
        data=sensors.get_sensors_dump_dict())


@app.route('/log')
def log():
    return render_template(
        'log.html',
        async_mode=sio.async_mode,
        data=sensors.get_sensors_dump_dict())


##
## start scheduler
##

scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func=sensors.update_sensors_ttl,
    trigger=IntervalTrigger(seconds=1),
    id='ttl_job',
    name='update ttl counters every second',
    replace_existing=True)

##
## start http server
##


def run_server(addr, port):
    log = LoggingLogAdapter(logger, level=logging.DEBUG)
    errlog = LoggingLogAdapter(logger, level=logging.ERROR)
    http_server = WSGIServer((addr, port), app, log=log, error_log=errlog)
    http_server.serve_forever()


logger.info("http server listen {}:{}".format(pars.addr, pars.port))
run_server(pars.addr, pars.port)
