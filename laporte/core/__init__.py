# -*- coding: utf-8 -*-
'''
Laporte sensors core
'''

import logging
import json
from apscheduler.schedulers.gevent import GeventScheduler
from flask_socketio import Namespace, emit, join_room, rooms
from laporte.app import app, sio, event_id
from laporte.metrics import metrics
from laporte.metrics.common import socketio_duration_metric
from laporte.core.sensors import METRICS_NAMESPACE, EVENTS_NAMESPACE
from laporte.core.sensors import Sensors

# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())

scheduler = GeventScheduler()
sensors = Sensors(app, sio, scheduler)

# SocketIO namespaces


class MetricsNamespace(Namespace):
    '''Socket.IO namespace for set/retrieve metrics of sensors'''
    @staticmethod
    @metrics.func_measure(**socketio_duration_metric,
                          labels={
                              'event': 'sensor_response',
                              'namespace': METRICS_NAMESPACE
                          })
    def on_sensor_response(message):
        '''
        receive metrics of changed sensors identified by node_id/sensor_id
        '''
        event_id.set(add_prefix='sio_')

        for node_id in message:
            node_data = message[node_id]
            logging.info('node update event: %s: %s', node_id, str(node_data))
            try:
                sensors.set_node_values(node_id, node_data)
            except KeyError:
                pass

    @staticmethod
    @metrics.func_measure(**socketio_duration_metric,
                          labels={
                              'event': 'sensor_addr_response',
                              'namespace': METRICS_NAMESPACE
                          })
    def on_sensor_addr_response(message):
        '''
        receive metrics of changed sensors identified by node_addr/key
        '''
        event_id.set(add_prefix='sio_')
        logging.info('addr/key update event: %s', message)

        for node_id, request_form in sensors.conv_addrs_to_ids(message).items():
            logging.debug('update %s: %s', node_id, str(request_form))
            try:
                sensors.set_node_values(node_id, request_form)
            except KeyError:
                pass

    @staticmethod
    @metrics.func_measure(**socketio_duration_metric,
                          labels={
                              'event': 'join',
                              'namespace': METRICS_NAMESPACE
                          })
    def on_join(message):
        '''fired upon gateway join'''

        logging.debug("SocketIO client join: %s", message)
        gw = message['room']
        join_room(gw)
        emit('status_response', {'joined in': rooms()})
        emit('config_response', {gw: list(sensors.get_config_of_gw(gw))})

    @staticmethod
    @metrics.func_measure(**socketio_duration_metric,
                          labels={
                              'event': 'connect',
                              'namespace': METRICS_NAMESPACE
                          })
    def on_connect():
        '''fired upon a successful connection'''

        emit('status_response', {'status': 'connected'})


class EventsNamespace(Namespace):
    '''Socket.IO namespace for events emit'''
    @staticmethod
    @metrics.func_measure(**socketio_duration_metric,
                          labels={
                              'event': 'connect',
                              'namespace': EVENTS_NAMESPACE
                          })
    def on_connect():
        '''emit initital event after a successful connection'''

        init_resp = {'data': sensors.get_metrics_dict_by_node(skip_None=False)}
        emit('init_response', json.dumps(init_resp), namespace=EVENTS_NAMESPACE)
        emit('hist_response', json.dumps(sensors.diff_buf), namespace=EVENTS_NAMESPACE)


sio.on_namespace(MetricsNamespace(METRICS_NAMESPACE))
sio.on_namespace(EventsNamespace(EVENTS_NAMESPACE))
