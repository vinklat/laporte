var jobs = {};

function sort_object(obj) {
    var items = Object.keys(obj).map(function (key) {
        return [key, obj[key]];
    });
    items.sort(function (first, second) {
        return second[1] - first[1];
    });
    var sorted_obj = {};
    $.each(items, function (k, v) {
        var use_key = v[0];
        var use_value = v[1];
        sorted_obj[use_key] = use_value;
    });
    return (sorted_obj);
}

function fill_jobs(msg) {
    var obj = JSON.parse(msg);
    var tnow = new Date();
    var node_id, sensor_id, metric;
    var out = "";

    for (node_id in obj) {
        for (sensor_id in obj[node_id]) {
            var sensor_label = node_id + "-" + sensor_id;

            for (metric in obj[node_id][sensor_id]) {
                //var metric_label = sensor_label + "_" + metric;
                // var id = "#" + metric_label;

                var value = obj[node_id][sensor_id][metric];

                switch (typeof value) {
                    case "number":
                        if (metric == "exp_timestamp") {
                            jobs[sensor_label + "-expire"] = value;
                        }
                        if (metric == "cron_timestamp") {
                            jobs[sensor_label + "-cron"] = value;
                        }
                        break;
                    case "object":
                        if (metric == "exp_timestamp") {
                            delete jobs[sensor_label + "-expire"];
                        }
                        if (metric == "cron_timestamp") {
                            delete jobs[sensor_label + "-cron"];
                        }
                        break;
                    default:
                        break;

                }
            }
        }
    }

    var ts;
    for (ts in sort_object(jobs)) {
        var t = new Date(jobs[ts] * 1000);
        var res = ts.split("-");
        var row = "<tr><td>" + t.toLocaleString(time_locale);
        row += "</td><td>" + res[2];
        row += "</td><td>" + res[0];
        row += "</td><td>" + res[1] + "</td></tr>";
        out = row + out;
    }
    $('#jobs').html(out);
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
        fill_jobs(msg);
    });

    socket.on('update_response', function (msg) {
        fill_jobs(msg);
    });
});

