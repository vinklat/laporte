#!/usr/bin/env python

from gevent import monkey
monkey.patch_all()
from flask import Flask, request, Response, abort, render_template, session
from flask_restful import Resource, Api
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect
from gevent.pywsgi import WSGIServer, LoggingLogAdapter
from argparse import ArgumentParser, ArgumentTypeError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from prometheus_client.core import REGISTRY
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import logging
from nodes import Nodes

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
    default='conf/nodes.yml')

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
nodes = Nodes(pars.sensors_fname)
REGISTRY.register(nodes.CustomCollector(nodes))

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


class MyNamespace(Namespace):
    def on_sensor_response(self, message):
        logger.debug('SocketIO: {} '.format(message))
        for node_id in message:
            request_form = message[node_id]
            logger.info('SocketIO in: {}: {}'.format(node_id,
                                                     str(request_form)))
            nodes.set_values(node_id, request_form)

    def on_join(self, message):
        join_room(message['room'])
        session['receive_count'] = session.get('receive_count', 0) + 1
        emit('status_response', {'joined in': rooms()})

    def on_connect(self):
        emit('status_response', {'status': 'connected'})

    def on_ping(self):
        emit('pong')


sio.on_namespace(MyNamespace('/metric'))
nodes.sio = sio

##
## REST API methods
##


class Metric(Resource):
    def put(self, node_id):
        try:
            logger.info("API: {}: {}".format(node_id,
                                             str(request.form.to_dict())))
            ret = nodes.set_values(node_id, request.form)
        except KeyError:
            logger.warning("node {} not found".format(node_id))
            abort(404)  #not configured

        return ret


class Metrics(Resource):
    def get(self):
        return list(nodes.get_sensors())


class MetricsByNode(Resource):
    def get(self):
        return nodes.get_sensors_dict_by_node()


class MetricsBySensor(Resource):
    def get(self):
        return nodes.get_sensors_dict_by_sensor()


class MetricsByGroups(Resource):
    def get(self):
        return nodes.get_sensors_dict_by_group()


class MetricsByNodeGroup(Resource):
    def get(self, group_name):
        return nodes.get_sensors_dict_of_group_by_node(group_name)


class MetricsBySensorGroup(Resource):
    def get(self, group_name):
        return nodes.get_sensors_dict_of_group_by_sensor(group_name)


api.add_resource(Metric, '/api/metric/<string:node_id>')
api.add_resource(Metrics, '/api/metrics')
api.add_resource(MetricsByNode, '/api/metrics/by_node')
api.add_resource(MetricsBySensor, '/api/metrics/by_sensor')
api.add_resource(MetricsByGroups, '/api/metrics/by_groups')
api.add_resource(MetricsByNodeGroup,
                 '/api/metrics/by_node/group/<string:group_name>')
api.add_resource(MetricsBySensorGroup,
                 '/api/metrics/by_sensor/group/<string:group_name>')


class ConfigNodesByInput(Resource):
    def get(self):
        return nodes.get_config_dict_by_inputs()


class ConfigNodesInput(Resource):
    def get(self, input):
        ret = nodes.get_config_dict_input(input)
        if not ret:
            logger.warning("input {} not configured".format(input))
            abort(404)
        return ret


class ConfigNodesGroup(Resource):
    def get(self, group):
        ret = nodes.get_nodes_list_of_group(group)
        if not ret:
            logger.warning("{}: group not configured".format(group))
            abort(404)
        return ret


api.add_resource(ConfigNodesByInput, '/api/config/nodes')
api.add_resource(ConfigNodesInput, '/api/config/nodes/input/<string:input>')
api.add_resource(ConfigNodesGroup, '/api/config/nodes/group/<string:group>')

##
## Web
##


@app.route('/')
def index():
    return render_template('index.html', async_mode=sio.async_mode)


##
## start scheduler
##

scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func=nodes.update_sensors_ttl,
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
