import logging
import json
import socketio
from laporte.client.metrics import (laporte_responses_total, laporte_connects_total)

METRICS_NAMESPACE = '/metrics'
EVENTS_NAMESPACE = '/events'

# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())


class MetricsNamespace(socketio.ClientNamespace):
    '''class-based Socket.IO event handlers for metrics'''

    gateways = []

    @staticmethod
    def default_actuator_handler(gateway, node_id, sensors):
        '''default function launched upon an actuator response node_id/sensor_id'''

        del sensors  # Ignored parameter
        logging.debug("empty default_actuator_handler for %s in %s", node_id, gateway)

    @staticmethod
    def default_actuator_addr_handler(gateway, node_addr, keys):
        '''default function launched upon an actuator response node_addr/key'''

        del keys  # Ignored parameter
        logging.debug("empty default_actuator_addr_handler for %s in %s", node_addr,
                      gateway)

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

        laporte_responses_total.labels('actuator_response', METRICS_NAMESPACE).inc()
        for gateway, nodes in json.loads(data).items():
            for node_id, sensors in nodes.items():
                self.actuator_handler(gateway, node_id, sensors)

    def on_actuator_addr_response(self, data):
        '''receive metrics of changed actuators identified by node_addr/key'''

        laporte_responses_total.labels('actuator_addr_response', METRICS_NAMESPACE).inc()
        for gateway, nodes in json.loads(data).items():
            for node_addr, keys in nodes.items():
                self.actuator_addr_handler(gateway, node_addr, keys)

    def on_config_response(self, data):
        '''TODO: receive sensor configuration from laporte (after room join)'''

        laporte_responses_total.labels('config_response', METRICS_NAMESPACE).inc()
        self.config_handler(data)

    @staticmethod
    def on_status_response(data):
        '''receive and log status message from laporte'''

        laporte_responses_total.labels('status_response', METRICS_NAMESPACE).inc()
        logging.info("Laporte %s namespace status response: %s", METRICS_NAMESPACE, data)

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

        logging.debug("empty default_update_handler for %s with %s chenged metrics",
                      node_id, len(sensors))

    init_handler = default_init_handler
    update_handler = default_update_handler

    def on_init_response(self, json_msg):
        '''receive update of nodes from laporte'''

        msg = json.loads(json_msg)
        try:
            data = msg['data']
        except KeyError as exc:
            logging.error('invalid message: %s', exc)
            return

        laporte_responses_total.labels('init_response', EVENTS_NAMESPACE).inc()
        self.init_handler(data)

    def on_event_response(self, json_msg):
        '''receive update of nodes event from laporte'''

        msg = json.loads(json_msg)
        try:
            # time = msg['time']
            # event_id = msg['event_id']
            data = msg['data']
        except KeyError as exc:
            logging.error('invalid message: %s', exc)
            return

        laporte_responses_total.labels('event_response', EVENTS_NAMESPACE).inc()
        for node_id, metrics in data.items():
            self.update_handler(node_id, metrics)

    @staticmethod
    def on_status_response(data):
        '''receive and log status message from laporte'''

        laporte_responses_total.labels('status_response', EVENTS_NAMESPACE).inc()
        logging.info("Laporte %s namespace status response: %s", METRICS_NAMESPACE, data)


class DefaultNamespace(socketio.ClientNamespace):
    '''class-based Socket.IO event handlers for default responses'''
    @staticmethod
    def on_connect():
        '''fired upon a successful connection'''

        logging.info("Laporte connected OK")
        laporte_connects_total.labels('laporte').inc()

    @staticmethod
    def on_reconnect():
        '''fired upon a successful reconnection'''

        logging.info("Laporte reconnected OK")
        laporte_connects_total.labels('laporte').inc()

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

        laporte_responses_total.labels('status_response', '/').inc()
        logging.info("Laporte status response: %s", data)

    @staticmethod
    def on_reload_response(data):
        '''receive reload response from laporte'''

        del data  # Ignored parameter
        laporte_responses_total.labels('reload_response   ', '/').inc()
        logging.info("Laporte was reloaded")
