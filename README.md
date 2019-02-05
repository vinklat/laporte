# Switchboard

- a gateway for processing metrics with automation and states
- acceptor for sensors, batch jobs or messages
- with the ability to set actuators
- compatible with Prometheus for metric alerting, collecting and data visualization
 
## Schema:

![switchboard schema](doc/switchboard_schema.svg)

## Features:

 - can evaluate, recalculate or correct metric
 - calculate new metric or state from other metrics
 - automation using a true algorithmization + data structures (python expression code)
 - can set TTL for metrics (obsolete metric disappears when time is over)
 - communicates via:
    * RESTful API 
    * realtime, bidirectionally using Socket.IO
    * exporting data as Prometheus metrics
    * live www status page
 - optional bridges (extensions):
    * [switchboard-mqtt](https://github.com/vinklat/switchboard-mqtt) to connect a large family of devices using MQTT protocol
    * switchboard-journal to store all events into database for forensic purposes (not done)
    * switchboard-panel to invoke and display states using a web page (not done)

## Quick HOWTO:
### Example:

We have the following scenario:  

![switchboard schema](doc/example_switch1.svg)

- two on/off switches
- the light is active when at least one switch is turned on

#### 1) run docker image:
`docker run -p 9128:9128 xvin/switchboard -c conf/example_switch1.yml`

(the content of this config file can be seen here [example_switch1.yml](conf/example_switch1.yml))

#### 2) hit switches:

you can control switches via REST API using curl:  

```
curl http://localhost:9128/api/metrics/switch1 -d "switch_state=on" -X PUT
curl http://localhost:9128/api/metrics/switch1 -d "switch_state=off" -X PUT
```
#### 3) watch status
 - live status page: [http://localhost:9128](http://localhost:9128)
 - JSON response of REST API: [http://localhost:9128/api/metrics/by_node](http://localhost:9128/api/metrics/by_node)
 - prometheus metrics: [http://localhost:9128/metrics](http://localhost:9128/metrics)

