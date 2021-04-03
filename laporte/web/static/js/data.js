/* global 
    io, locale, fmtMSS, renderTime
*/

var countdowns = {};

function do_metric(metric, sensor_label, value, tnow) {
    const metric_label = sensor_label + "_" + metric;
    const id = "#" + metric_label;

    switch (typeof value) {
        case "number":
            if (metric === "duration_seconds") {
                value = Math.round(value * 10) / 10;
                if (value === 0) {
                    $(id).html("");
                } else {
                    $(id).html(`${value}s`);
                }
            } else if (metric === "hits_total") {
                if (value === 0) {
                    $(id).html("");
                } else {
                    $(id).html(`${value}&#xd7;`);
                }
            } else if (metric === "exp_timestamp") {
                countdowns[sensor_label] = Math.round(value - tnow / 1000);
            } else if (metric === "hit_timestamp") {
                var t = new Date(value * 1000);
                $(id).html(`(last ${renderTime(t)})`);
            } else {
                value = Math.round(value * 100) / 100;
                $(id).html(value.toString());
            }
            break;
        case "string":
            $(id).html(value);
            break;
        case "boolean":
            $(id).html(value ? "true" : "false");
            break;
        case "object":
            // if exp_timestamp is null
            if (metric === "exp_timestamp") {
                delete countdowns[sensor_label];
                $("#" + sensor_label + "_ttl").html("");
            } else {
                $(id).html("");
            }
            break;
        default:
            $(id).html("");
            break;

    }
}

function fill_metrics(msg) {
    const event_data = JSON.parse(msg).data;
    const tnow = new Date();

    for (var node_id in event_data) {
        if (event_data.hasOwnProperty(node_id)) {
            for (var sensor_id in event_data[node_id]) {
                if (event_data[node_id].hasOwnProperty(sensor_id)) {
                    const sensor_label = (node_id + "_" + sensor_id).replace(/\./g, "-");
                    for (var metric in event_data[node_id][sensor_id]) {
                        if (event_data[node_id][sensor_id].hasOwnProperty(metric)) {
                            const value = event_data[node_id][sensor_id][metric];
                            do_metric(metric, sensor_label, value, tnow);
                        }
                    }
                }
            }
        }
    }
}

$(document).ready(function () {
    // Connect to the Socket.IO server.
    const namespace = "/events";
    const sio_url = `${location.protocol}//${document.domain}:${location.port}${namespace}`;
    var socket = io.connect(sio_url);

    // Event handlers:
    socket.on('connect', function () {
        $('#status').html("connected");
    });

    // Event handler for lost connection.
    socket.on('disconnect', function () {
        $('#status').html("not connected");
    });

    // Event handler: server sent all data.
    socket.on('init_response', function (msg) {
        fill_metrics(msg);
    });

    // Event handler for server sent event data.
    socket.on('event_response', function (msg) {
        fill_metrics(msg);
    });
});

/* jshint unused: false */
var timer = setInterval(function () {
    var x;
    for (x in countdowns) {
        if (countdowns[x] > 0) {
            $("#" + x + "_ttl").html("(exp " + fmtMSS(countdowns[x]) + ")");
            countdowns[x] -= 1;
        } else {
            delete countdowns[x];
            $("#" + x + "_ttl").html("");
        }
    }
}, 1000);