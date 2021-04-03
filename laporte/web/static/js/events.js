/* global 
    io, followLogs, scrollToBottomAnimate, scrollToBottomInstant, renderTime
*/


function render_value(metric, value) {
    var ret = value;

    switch (typeof value) {
        case "number":
            if (metric.includes("_seconds")) {
                ret = `${Math.round(value * 1000) / 1000}s`;
            }
            else if (metric.includes("_total")) {
                ret = `${value}&#xd7;`;
            }
            else if (metric.includes("_timestamp")) {
                const time = new Date(value * 1000);
                ret = renderTime(time);
            }
            else {
                ret = `${Math.round(value * 10000) / 10000}`;
            }
            break;
        case "object":
            // if exp_timestamp is null
            if (metric === "exp_timestamp") {
                ret = "<i>expired</i>";
            }
    }
    return (ret);
}

var odd_row_fl = false;

function render_log(log) {
    const { time, event_id, data } = log;
    const tlog = new Date(time * 1000);
    var tstr = renderTime(tlog);
    var metrics_total = 0;
    var node_rowspans = {};
    var sensor_rowspans = {};
    odd_row_fl = !odd_row_fl;

    var row = "";
    const event_td = `
        <td rowspan=metrics_total>${tstr}</td>
        <td rowspan=metrics_total class="font-weight-light">${event_id}</td>
    `;
    var new_event_fl = true;
    for (var node_id in data) {
        if (data.hasOwnProperty(node_id)) {
            var new_node_fl = true;
            node_rowspans[node_id] = 0;
            const node_td = `<td rowspan=${node_id}>${node_id}</td>`;

            for (var sensor_id in data[node_id]) {
                if (data[node_id].hasOwnProperty(sensor_id)) {
                    var new_sensor_fl = true;
                    const sensor_label = `${node_id}_${sensor_id}`;
                    sensor_rowspans[sensor_label] = 0;
                    const sensor_td = `<td rowspan=${sensor_label}>${sensor_id}</td>`;

                    for (var metric in data[node_id][sensor_id]) {
                        if (data[node_id][sensor_id].hasOwnProperty(metric)) {
                            const value = render_value(metric, data[node_id][sensor_id][metric]);
                            row += `
                            <tr ${!odd_row_fl && 'class="odd-row"'}>
                                ${new_event_fl && event_td}
                                ${new_node_fl && node_td}
                                ${new_sensor_fl && sensor_td}
                                <td>${metric}</td>
                                <td>${value}</td>
                            </tr>
                            `;
                            metrics_total += 1;
                            sensor_rowspans[sensor_label] += 1;
                            node_rowspans[node_id] += 1;
                            new_node_fl = false;
                            new_sensor_fl = false;
                            new_event_fl = false;
                        }
                    }
                    row = row.replace(`rowspan=${sensor_label}`, `rowspan=${sensor_rowspans[sensor_label]}`);
                }
            }
            row = row.replace(`rowspan=${node_id}`, `rowspan=${node_rowspans[node_id]}`);
        }
    }
    row = row.replaceAll("rowspan=metrics_total", `rowspan=${metrics_total}`);

    return row;
}

function print_batch_log(logs) {
    if (logs && logs.length) {
        var result = "";
        logs.forEach(log => result = result.concat(render_log(log)));
        $('#log').append(result);
    }
}

function print_log(log) {
    const row = render_log(log);
    $('#log').append(row);
}

$(document).ready(function () {
    // Connect to the Socket.IO server.
    const namespace = "/events";
    const sio_url = `${location.protocol}//${document.domain}:${location.port}${namespace}`;
    var socket = io.connect(sio_url);

    // Event handler for new connections.
    socket.on("connect", function () {
        $("#status").html("connected");
    });

    // Event handler for lost connection.
    socket.on("disconnect", function () {
        $("#status").html("not connected");
    });

    // Event handler: server sent old logs from the buffer.
    socket.on('hist_response', function (msg) {
        var buf = JSON.parse(msg);

        $('#log').html('');
        print_batch_log(buf);

        scrollToBottomInstant();
    });

    // Event handler: server sent a realtime log
    socket.on('event_response', function (msg) {
        var log = JSON.parse(msg);
        print_log(log);

        if (followLogs()) {
            scrollToBottomAnimate();
        }
    });
});