# -*- coding: utf-8 -*-
'''objects that create a Socket.OI client for Laporte'''

import logging
import json
import socketio
from prometheus_client import Counter

METRICS_NAMESPACE = '/metrics'
EVENTS_NAMESPACE = '/events'

# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())

c_responses_total = Counter('laporte_responses_total',
                            'Total count of Socket.IO responses',
                            ['response', 'namespace'])
c_emits_total = Counter('laporte_emits_total',
                        'Total count of Socket.IO emits',
                        ['response', 'namespace'])
c_connects_total = Counter('laporte_connects_total',
                           'Total count of connects/reconnects', ['service'])


class MetricsNamespace(socketio.ClientNamespace):
    '''class-based Socket.IO event handlers for metrics'''

    gateways = []

    @staticmethod
    def default_actuator_handler(gateway, node_id, sensors):
        '''default function launched upon an actuator response node_id/sensor_id'''

        del sensors  # Ignored parameter
        logging.debug("empty default_actuator_handler for %s in %s", node_id,
                      gateway)

    @staticmethod
    def default_actuator_addr_handler(gateway, node_addr, keys):
        '''default function launched upon an actuator response node_addr/key'''

        del keys  # Ignored parameter
        logging.debug("empty default_actuator_addr_handler for %s in %s",
                      node_addr, gateway)

    @staticmethod
    def default_config_handler(data):
        '''default function launched upon an gateway config response'''

        gateway = next(iter(data))
        logging.debug("empty default_config_handler for %s", gateway)

    actuator_handler = default_actuator_handler
    actuator_addr_handler = default_actuator_addr_handler
    config_handler = default_config_handler

    def on_actuator_response(self, data):
        '''receive metrics of changed actuators identified by node_id/sensor_id'''

        c_responses_total.labels('actuator_response', METRICS_NAMESPACE).inc()
        for gateway, nodes in json.loads(data).items():
            for node_id, sensors in nodes.items():
                self.actuator_handler(gateway, node_id, sensors)

    def on_actuator_addr_response(self, data):
        '''receive metrics of changed actuators identified by node_addr/key'''

        c_responses_total.labels('actuator_addr_response',
                                 METRICS_NAMESPACE).inc()
        for gateway, nodes in json.loads(data).items():
            for node_addr, keys in nodes.items():
                self.actuator_addr_handler(gateway, node_addr, keys)

    def on_config_response(self, data):
        '''TODO: receive sensor configuration from laporte (after room join)'''

        c_responses_total.labels('config_response', METRICS_NAMESPACE).inc()
        self.config_handler(data)

    @staticmethod
    def on_status_response(data):
        '''receive and log status message from laporte'''

        c_responses_total.labels('status_response', METRICS_NAMESPACE).inc()
        logging.info("Laporte %s namespace status response: %s",
                     METRICS_NAMESPACE, data)

    def __join_gateways(self):
        '''join Socket.IO rooms called as same as gateways'''

        for gw_name in self.gateways:
            self.emit("join", {'room': gw_name})

    def on_connect(self):
        '''fired upon a successful connection'''

        self.__join_gateways()

    def on_reconnect(self):
        '''fired upon a successful reconnection'''

        self.__join_gateways()


class EventsNamespace(socketio.ClientNamespace):
    '''class-based Socket.IO event handlers for events'''

    @staticmethod
    def default_init_handler(nodes):
        '''
        Default function launched upon an init response.

        Args:
            nodes (Dict[str: Dict[str: Dict[str: Any]]]):
                dicts of node_ids with dict of sensor_ids with dicts of changed metrics
        '''

        logging.debug("empty default_init_handler for %d nodes", len(nodes))

    @staticmethod
    def default_update_handler(node_id, sensors):
        '''
        Default function launched upon an update response.

        Args:
            node_id (str):
                a node with changed metrics
            sensors (Dict[str: Dict[str: Any]]):
                dict of sensor_ids with dicts of changed metrics
        '''

        logging.debug(
            "empty default_update_handler for %s with %s chenged metrics",
            node_id, len(sensors))

    init_handler = default_init_handler
    update_handler = default_update_handler

    def on_init_response(self, data):
        '''receive update of nodes from laporte'''

        c_responses_total.labels('init_response', EVENTS_NAMESPACE).inc()
        self.init_handler(json.loads(data))

    def on_update_response(self, data):
        '''receive update of nodes from laporte'''

        c_responses_total.labels('update_response', EVENTS_NAMESPACE).inc()
        for node_id, metrics in json.loads(data).items():
            self.update_handler(node_id, metrics)

    @staticmethod
    def on_status_response(data):
        '''receive and log status message from laporte'''

        c_responses_total.labels('status_response', EVENTS_NAMESPACE).inc()
        logging.info("Laporte %s namespace status response: %s",
                     METRICS_NAMESPACE, data)


class DefaultNamespace(socketio.ClientNamespace):
    '''class-based Socket.IO event handlers for default responses'''

    @staticmethod
    def on_connect():
        '''fired upon a successful connection'''

        logging.info("Laporte connected OK")
        c_connects_total.labels('laporte').inc()

    @staticmethod
    def on_reconnect():
        '''fired upon a successful reconnection'''

        logging.info("Laporte reconnected OK")
        c_connects_total.labels('laporte').inc()

    @staticmethod
    def on_disconnect():
        '''fired upon a disconnection'''

        logging.info("Laporte disconnected")

    @staticmethod
    def on_error():
        '''fired upon a connection error'''

        logging.error("Socket.IO connection error")

    @staticmethod
    def on_status_response(data):
        '''receive and log status message from laporte'''

        c_responses_total.labels('status_response', '/').inc()
        logging.info("Laporte status response: %s", data)

    @staticmethod
    def on_reload_response(data):
        '''receive reload response from laporte'''

        del data  # Ignored parameter
        c_responses_total.labels('reload_response   ', '/').inc()
        logging.info("Laporte was reloaded")


class LaporteClient():
    '''Object containing Socket.IO client with registered namespaces.'''

    def __init__(self, addr, port, gateways=None, events=False):
        '''
        Connect to the laporte server.

            addr (str):
                Hostname or IP of laporte server.
            port (int):
                 Port of laporte server.
            gateways (Optional[List[str]]):
                List of gateways to be joined in.
                Defaults to None. Register metrics namespece if set.
            events (Optional[bool]):
                Register events namespace. Defaults to False.
        '''

        namespaces = []
        self.sio = socketio.Client(logger=True, engineio_logger=True)
        self.ns_default = DefaultNamespace('/')
        self.ns_metrics = MetricsNamespace(METRICS_NAMESPACE)
        self.ns_events = EventsNamespace(EVENTS_NAMESPACE)
        self.sio.register_namespace(self.ns_default)

        if isinstance(gateways, list):
            namespaces.append(METRICS_NAMESPACE)
            self.ns_metrics.gateways = gateways
            self.sio.register_namespace(self.ns_metrics)

        if events:
            namespaces.append(EVENTS_NAMESPACE)
            self.sio.register_namespace(self.ns_events)

        self.sio.connect('http://{}:{}'.format(addr, port),
                         namespaces=namespaces)

    def loop(self):
        '''main loop for Socket.IO client'''

        self.sio.wait()

    def emit(self, response, message, namespace=METRICS_NAMESPACE):
        '''emit custom response to the Laporte'''

        logging.info("Laporte emit: %s %s", response, message)
        c_emits_total.labels(response, namespace).inc()
        self.sio.emit(response, message, namespace=namespace)
