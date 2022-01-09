# -*- coding: utf-8 -*-
'''
Laporte client prometheus counters
'''

from prometheus_client import Counter

laporte_responses_total = Counter('socketio_client_responses_total',
                                  'Total count of Socket.IO responses',
                                  ['response', 'namespace'])

laporte_emits_total = Counter('socketio_client_emits_total',
                              'Total count of Socket.IO emits',
                              ['response', 'namespace'])

laporte_connects_total = Counter('socketio_client_connects_total',
                                 'Total count of connects/reconnects', ['service'])
