# -*- coding: utf-8 -*-
'''
Laporte client prometheus counters
'''

from prometheus_client import Counter

c_responses_total = Counter('laporte_responses_total',
                            'Total count of Socket.IO responses',
                            ['response', 'namespace'])

c_emits_total = Counter('laporte_emits_total', 'Total count of Socket.IO emits',
                        ['response', 'namespace'])

c_connects_total = Counter('laporte_connects_total',
                           'Total count of connects/reconnects', ['service'])
