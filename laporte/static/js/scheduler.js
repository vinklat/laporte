/* global 
    io, locale
*/

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
    var out = "";

    for (var node_id in obj) {
        if (obj.hasOwnProperty(node_id)) {
            for (var sensor_id in obj[node_id]) {
                if (obj[node_id].hasOwnProperty(sensor_id)) {
                    var sensor_label = node_id + "-" + sensor_id;
                    for (var metric in obj[node_id][sensor_id]) {
                        if (obj[node_id][sensor_id].hasOwnProperty(metric)) {
                            var value = obj[node_id][sensor_id][metric];

                            switch (typeof value) {
                                case "number":
                                    if (metric === "exp_timestamp") {
                                        jobs[sensor_label + "-expire"] = value;
                                    }
                                    if (metric === "cron_timestamp") {
                                        jobs[sensor_label + "-cron"] = value;
                                    }
                                    break;
                                case "object":
                                    if (metric === "exp_timestamp") {
                                        delete jobs[sensor_label + "-expire"];
                                    }
                                    if (metric === "cron_timestamp") {
                                        delete jobs[sensor_label + "-cron"];
                                    }
                                    break;
                                default:
                                    break;

                            }
                        }
                    }
                }
            }
        }
    }

    var ts;
    for (ts in sort_object(jobs)) {
        if (jobs.hasOwnProperty(ts)) {

            var t = new Date(jobs[ts] * 1000);
            var res = ts.split("-");
            const row = `
            <tr class="table-light">
                <td>
                    ${t.toLocaleString(locale)}
                </td>
                <td>
                    ${res[0]}
                </td>
                <td>
                    ${res[1]}
                </td>
                <td>
                    ${res[2]}
                </td>
            </tr>
        `;
            out = row + out;
        }
    }
    $('#jobs').html(out);
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
        fill_jobs(msg);
    });

    // Event handler for server sent event data.
    socket.on('update_response', function (msg) {
        fill_jobs(msg);
    });
});

