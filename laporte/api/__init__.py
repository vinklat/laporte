# -*- coding: utf-8 -*-
'''
Flask blueprint and resources of Laporte REST API v1
'''

import logging
from flask import Blueprint, request
from flask_restx import Api, Resource, abort
from laporte.argparser import pars
from laporte.version import __version__, get_version_info, get_runtime_info
from laporte.app import event_id
from laporte.metrics import metrics
from laporte.metrics.common import http_duration_metric
from laporte.core import sensors

# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())

api_bp = Blueprint('api', __name__, url_prefix='/api')
api = Api(api_bp, doc=False, title='Laporte API', version=__version__)

# url prefix /api/metrics/...

ns_metrics = api.namespace('metrics',
                           description='methods for manipulating metrics',
                           path='/metrics')

parser = api.parser()
for sensor_id, t, t_str in sensors.get_parser_arguments():
    parser.add_argument(sensor_id,
                        type=t,
                        required=False,
                        help=f'{t_str} value for sensor {sensor_id}',
                        location='form')


@ns_metrics.route('/<string:node_id>')
class NodeMetrics(Resource):
    @api.doc(params={'node_id': 'a node to be affected'})
    @api.response(200, 'Success')
    @api.response(404, 'Node or sensor not found')
    @api.expect(parser)
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'put',
                              'location': '/api/metrics/<node_id>'
                          })
    def put(self, node_id):
        '''set sensors of a node'''

        event_id.set(add_prefix='api_')
        logging.info("node update request: %s: %s", node_id, str(request.form.to_dict()))
        try:
            ret = sensors.set_node_values(node_id, request.form)
        except KeyError:
            logging.warning("node %s or sensor not found", node_id)
            abort(404)  # sensor not configured
        event_id.release()

        return ret

    @api.doc(params={'node_id': 'a node from which to get metrics'})
    @api.response(200, 'Success')
    @api.response(404, 'Node not found')
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'get',
                              'location': '/api/metrics/<node_id>'
                          })
    def get(self, node_id):
        '''get sensor metrics of a node'''

        try:
            ret = dict(sensors.get_metrics_of_node(node_id))
        except KeyError:
            logging.warning("node %s not found", node_id)
            abort(404)  # sensor not configured

        return ret


@ns_metrics.route('/inc/<string:node_id>')
class IncNodeMetrics(Resource):
    @api.doc(params={'node_id': 'a node to be affected'})
    @api.response(200, 'Success')
    @api.response(404, 'Node or sensor not found')
    @api.expect(parser)
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'put',
                              'location': '/api/metrics/inc/<node_id>'
                          })
    def put(self, node_id):
        '''increment sensor values of a node'''
        logging.info("API/inc: %s: %s", node_id, str(request.form.to_dict()))
        try:
            ret = sensors.set_node_values(node_id, request.form, increment=True)
        except KeyError:
            logging.warning("node %s or sensor not found", node_id)
            abort(404)  # sensor not configured

        return ret


@ns_metrics.route('/<string:node_id>/<string:sensor_id>')
class SensorMetrics(Resource):
    @api.doc(
        params={
            'node_id': 'a node where a sensor belongs',
            'sensor_id': 'a sensor from which to get metrics'
        })
    @api.response(200, 'Success')
    @api.response(404, 'Node or sensor not found')
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'get',
                              'location': '/api/metrics/inc/<node_id>'
                          })
    def get(self, search_node_id, search_sensor_id):
        '''get metrics of one sensor'''

        try:
            ret = dict(sensors.get_metrics_of_sensor(search_node_id, search_sensor_id))
        except KeyError:
            logging.warning("node %s or sensor %s not found", search_node_id,
                            search_sensor_id)
            abort(404)  # sensor not configured

        return ret


@ns_metrics.route('/')
class SensorsMetricsList(Resource):
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'get',
                              'location': '/api/metrics'
                          })
    def get(self):
        '''get a list of all metrics'''

        return list(sensors.get_metrics(skip_None=False))


@ns_metrics.route('/by_gw')
class SensorsMetricsByGw(Resource):
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'get',
                              'location': '/api/metrics/by_gw'
                          })
    def get(self):
        '''get all metrics sorted by gateway / node_id / sensor_id'''

        return sensors.get_metrics_dict_by_gw(skip_None=False)


@ns_metrics.route('/by_node')
class SensorsMetricsByNode(Resource):
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'get',
                              'location': '/api/metrics/by_node'
                          })
    def get(self):
        '''get all metrics sorted by node_id / sensor_id'''

        return sensors.get_metrics_dict_by_node(skip_None=False)


@ns_metrics.route('/by_sensor')
class SensorsMetricsBySensor(Resource):
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'get',
                              'location': '/api/metrics/by_sensor'
                          })
    def get(self):
        '''get all metrics sorted by sensor_id'''

        return sensors.get_metrics_dict_by_sensor(skip_None=False)


# url prefix /api/state/...

ns_state = api.namespace('state',
                         description='methods for manipulating process state',
                         path='/state')


@ns_metrics.route('/default')
class StateDefault(Resource):
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'put',
                              'location': '/api/state/default'
                          })
    def put(self):
        '''reset state of all sensors to default value
           (reset metric "value")'''

        return sensors.default_values()


@ns_metrics.route('/reset')
class StateReset(Resource):
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'put',
                              'location': '/api/state/reset'
                          })
    def put(self):
        '''reset state and metadata of all sensors
           (reset metrics "value", "hits_total",
           "hit_timestamp", "duration_seconds")'''

        return sensors.reset_values()


@ns_state.route('/reload')
class StateReload(Resource):
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'put',
                              'location': '/api/state/reload'
                          })
    def put(self):
        '''reload laporte configuration'''

        return sensors.reload_config(pars)


@ns_state.route('/dump')
class StateDump(Resource):
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'get',
                              'location': '/api/state/dump'
                          })
    def get(self):
        '''get all data of all sensors'''

        return sensors.get_sensors_dump_dict()


# url prefix /api/info/...

ns_info = api.namespace('info',
                        description='methods to obtain application information',
                        path='/info')


@ns_info.route('/version')
class InfoVersion(Resource):
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'get',
                              'location': '/api/info/version'
                          })
    def get(self):
        '''get application version info'''

        return get_version_info()


@ns_info.route('/runtime')
class InfoRuntime(Resource):
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'get',
                              'location': '/api/info/runtime'
                          })
    def get(self):
        '''get application runtime resources and info'''

        return get_runtime_info()


@ns_info.route('/myip')
class InfoIP(Resource):
    @metrics.func_measure(**http_duration_metric,
                          labels={
                              'method': 'get',
                              'location': '/api/info/myip'
                          })
    def get(self):
        '''show my IP address + other client info'''

        ret = {
            'ip': request.remote_addr,
            'user-agent': request.user_agent.string,
            'platform': request.user_agent.platform,
            'browser': request.user_agent.browser,
            'version': request.user_agent.version
        }

        return ret
