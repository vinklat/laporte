# -*- coding: utf-8 -*-
'''
Common prometheus metrics presets
'''

from laporte.version import app_name

log_message_metric = {
    'prefix': app_name,
    'name': 'log_messages',
    'suffix': 'total',
    'help_str': 'number of messages logged'
}

http_duration_metric = {
    'prefix': 'http',
    'name': 'request_duration',
    'suffix': 'seconds',
    'help_str': 'duration of http request'
}

http_requests_metric = {
    'prefix': 'http',
    'name': 'requests',
    'suffix': 'total',
    'help_str': 'number of http requests received'
}

http_responses_metric = {
    'prefix': 'http',
    'name': 'responses',
    'suffix': 'total',
    'help_str': 'number of http responses sent'
}

http_exception_responses_metric = {
    'prefix': 'http',
    'name': 'exception_responses',
    'suffix': 'total',
    'help_str': 'number of exceptions during http responses'
}

socketio_duration_metric = {
    'prefix': 'socketio',
    'name': 'event_duration',
    'suffix': 'seconds',
    'help_str': 'duration of Socket.IO event'
}
