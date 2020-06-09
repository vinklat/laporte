var countdowns = {};

function fill_metrics(msg) {
    var obj = JSON.parse(msg);
    var tnow = new Date();
    var tnowzero = tnow - (60 * 60 * 1000 * tnow.getHours()) - (60 * 1000 * tnow.getMinutes()) - (1000 * tnow.getSeconds());
    var node_id, sensor_id, metric;

    for (node_id in obj) {
        for (sensor_id in obj[node_id]) {
            var sensor_label = (node_id + "_" + sensor_id).replace(/\./g, "-");

            for (metric in obj[node_id][sensor_id]) {
                var metric_label = sensor_label + "_" + metric;
                var id = "#" + metric_label;
                var value = obj[node_id][sensor_id][metric];

                switch (typeof value) {
                    case "number":
                        if (metric == "duration_seconds") {
                            value = Math.round(value * 10) / 10;
                            if (value == 0) {
                                $(id).html("");
                            } else {
                                $(id).html(value.toString() + "s");
                            }
                        } else if (metric == "hits_total") {
                            if (value == 0) {
                                $(id).html("");
                            } else {
                                $(id).html(value.toString() + "&#xd7;");
                            }
                        } else if (metric == "exp_timestamp") {
                            countdowns[sensor_label] = Math.round(value - tnow/1000);
                        } else if (metric == "hit_timestamp") {
                            var t = new Date(value * 1000);
                            var s;
                            if (t > tnowzero) {
                                s = t.toLocaleTimeString(time_locale);
                            } else {
                                s = t.toLocaleString(time_locale);
                            }
                            $(id).html("(last " + s + ")");
                        } else {
                            value = Math.round(value * 100) / 100;
                            $(id).html(value.toString());
                        }
                        break;
                    case "string":
                        $(id).html(value);
                        break;
                    case "boolean":
                        value ? $(id).html("true") : $(id).html("false");
                        break;
                    case "object":
                        // if exp_timestamp is null
                        if (metric == "exp_timestamp") {
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
        }
    }
}

$(document).ready(function () {
    var namespace = '/events';
    // Connect to the Socket.IO server.
    // The connection URL has the following format:
    //     http[s]://<domain>:<port>[/<namespace>]
    var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port + namespace);

    // Event handlers:
    socket.on('connect', function () {
        $('#status').html("connected");
    });

    socket.on('disconnect', function () {
        $('#status').html("not connected");
    });

    socket.on('init_response', function (msg) {
        fill_metrics(msg);
    });

    socket.on('update_response', function (msg) {
        fill_metrics(msg);
    });
});

function fmtMSS(s) {
    return (s - (s %= 60)) / 60 + (9 < s ? ':' : ':0') + s;
}

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