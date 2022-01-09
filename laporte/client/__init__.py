# -*- coding: utf-8 -*-
'''
Objects that create a Socket.OI client for Laporte
'''

import logging
from time import sleep
import socketio
from laporte.client.metrics import laporte_emits_total
from laporte.client.sio import (DefaultNamespace, MetricsNamespace, EventsNamespace,
                                METRICS_NAMESPACE, EVENTS_NAMESPACE)
# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())


class LaporteClient():
    '''
    Object containing Socket.IO client with registered namespaces.
    '''
    def __init__(self,
                 addr: str,
                 port: int,
                 gateways: list = None,
                 events: bool = False) -> None:
        '''
        Connect to the laporte server.

        Args:
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

        while True:
            try:
                self.sio.connect(f'http://{addr}:{port}', namespaces=namespaces)
            except socketio.exceptions.ConnectionError as exc:
                logging.error("%s", exc)
                sleep(10)
            else:
                break

    def loop(self):
        '''main loop for Socket.IO client'''

        self.sio.wait()

    def emit(self, response, message, namespace=METRICS_NAMESPACE):
        '''emit custom response to the Laporte'''

        logging.info("Laporte emit: %s %s", response, message)
        laporte_emits_total.labels(response, namespace).inc()
        self.sio.emit(response, message, namespace=namespace)
