'''
Flask blueprint and resources of Laporte web interface
'''

from flask import Blueprint, render_template
from laporte.version import __version__, get_runtime_info
from laporte.metrics import metrics
from laporte.metrics.common import http_duration_metric
from laporte.app import sio
from laporte.api import api
from laporte.core import sensors

web_bp = Blueprint('web',
                   __name__,
                   template_folder="templates",
                   static_folder="static",
                   static_url_path='/static')


@web_bp.route('/')
@web_bp.route('/data')
@metrics.func_measure(**http_duration_metric,
                      labels={
                          'method': 'get',
                          'location': '/data'
                      })
def data():
    return render_template('data.html',
                           async_mode=sio.async_mode,
                           data=sensors.get_sensors_dump_dict())


@web_bp.route('/events')
@metrics.func_measure(**http_duration_metric,
                      labels={
                          'method': 'get',
                          'location': '/events'
                      })
def events():
    return render_template('events.html', async_mode=sio.async_mode)


@web_bp.route('/status/info')
@metrics.func_measure(**http_duration_metric,
                      labels={
                          'method': 'get',
                          'location': '/status/info'
                      })
def status_info():

    return render_template('info.html', runtime=get_runtime_info())


@web_bp.route('/status/scheduler')
@metrics.func_measure(**http_duration_metric,
                      labels={
                          'method': 'get',
                          'location': '/status/scheduler'
                      })
def status_scheduler():
    return render_template('scheduler.html', async_mode=sio.async_mode)


@web_bp.route('/status/metrics')
@metrics.func_measure(**http_duration_metric,
                      labels={
                          'method': 'get',
                          'location': '/status/metrics'
                      })
def status_metrics():
    return render_template('metrics.html', async_mode=sio.async_mode)


@web_bp.route('/status/log')
@metrics.func_measure(**http_duration_metric,
                      labels={
                          'method': 'get',
                          'location': '/status/log'
                      })
def status_log():
    return render_template('log.html', async_mode=sio.async_mode)


@web_bp.route('/doc')
@metrics.func_measure(**http_duration_metric,
                      labels={
                          'method': 'get',
                          'location': '/doc'
                      })
@api.documentation
def doc():
    return render_template('doc.html', title=api.title, specs_url=api.specs_url)
