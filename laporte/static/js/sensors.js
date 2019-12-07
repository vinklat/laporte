function fill_metrics(msg) {
    obj = JSON.parse(msg);

    for (node_id in obj) {
        for (sensor_id in obj[node_id]) {
            var sensor_label = (node_id + "_" + sensor_id).replace(/\./g,"-");
            var sensor_type = sensors[sensor_label].type;
            var default_value = sensors[sensor_label].default_value;
            var ttl = sensors[sensor_label].ttl;
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
                        } else if (metric == "hit_timestamp") {
                            var t = new Date(value * 1000);
                            var tnow = new Date();
                            var tnowstart = tnow - (60 * 60 * 1000 * tnow.getHours()) - (60 * 1000 * tnow.getMinutes()) - (1000 * tnow.getSeconds())
                            var s;
                            if (t > tnowstart) {
                                s = t.toLocaleTimeString(time_locale);
                            } else {
                                s = t.toLocaleString(time_locale);
                            }
                            $(id).html("(last " + s + ")");
                            if ((typeof ttl == 'number') && ((sensor_type != 3) || (document.getElementById(sensor_label + "_value").innerHTML != default_value.toString()))) {
                                sensors[sensor_label].ttl_remaining = Math.round(ttl - ((tnow - t)/1000));
                            } else {
                                sensors[sensor_label].ttl_remaining = 0;
                            }
                        
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
                    default:
                        $(id).html("");
                        break;

                }
            }
        }
    }
}

$(document).ready(function() {
    var namespace = '/events';
    // Connect to the Socket.IO server.
    // The connection URL has the following format:
    //     http[s]://<domain>:<port>[/<namespace>]
    var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port + namespace);

    // Event handlers:
    socket.on('connect', function() {
        $('#status').html("connected");
    });

    socket.on('disconnect', function() {
        $('#status').html("not connected");
    });
 
    socket.on('init_response', function(msg) {
        fill_metrics(msg);
    });

    socket.on('update_response', function(msg) {
        fill_metrics(msg);
    });
});

function fmtMSS(s) {
    return (s - (s %= 60)) / 60 + (9 < s ? ':' : ':0') + s
}

var timer = setInterval(function() {
    for (x in sensors) {
        if (sensors[x].ttl_remaining > 0) {
            $("#" + x + "_ttl").html("(exp " + fmtMSS(sensors[x].ttl_remaining) + ")");
            sensors[x].ttl_remaining -= 1;
        } else {
            $("#" + x + "_ttl").html("");
        }
    }
}, 1000);