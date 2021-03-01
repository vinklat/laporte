/* global 
    io, followLogs, scrollToBottomInstant, scrollToBottomAnimate, logTrClass,
    htmlEncode, renderTime
*/

function render_log(log) {
    const { time, levelname, msg, event_id, funcname, filename, fileno } = log;
    const tlog = new Date(time * 1000);
    const long = msg.length > 320;
    const tstr = `${renderTime(tlog)}`;

    const trclass = logTrClass(levelname);
    const encodedMsg = htmlEncode(msg);

    const row = `
        <tr class="${trclass}">
            <td>
                ${tstr}
                <br/>
                <small class="text-secondary font-weight-light">${levelname}</small>
            </td>
            <td>
                <small>${event_id}</small>
            </td>
            <td>
                ${funcname}
                <br/>
                <small class="text-secondary font-weight-light">
                    (${filename}:${fileno})
                </small>
            </td>
            <td class="small text-break">
                <div ${long && 'class="truncate-overflow"'}>
                    <samp>${encodedMsg} </samp>
                </div>
            </td> 
        </tr>
    `;

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
    const namespace = "/logs";
    const sio_url = `${location.protocol}//${document.domain}:${location.port}${namespace}`;
    var socket = io.connect(sio_url);

    // Event handler for new connections.
    socket.on('connect', function () {
        $('#status').html("connected");
    });

    // Event handler for lost connection.
    socket.on('disconnect', function () {
        $('#status').html("not connected");
    });

    // Event handler: server sent old logs from the buffer.
    socket.on('hist_response', function (msg) {
        var buf = JSON.parse(msg);

        $('#log').html('');
        print_batch_log(buf);
        scrollToBottomInstant();
    });

    // Event handler: server sent a realtime log
    socket.on('log_response', function (msg) {
        var log = JSON.parse(msg);
        print_log(log);

        if (followLogs()) {
            scrollToBottomAnimate();
        }
    });

    // Toggle truncated
    $('#log').on('click', 'tr td div.truncate-overflow', function () {
        $(this).removeClass('truncate-overflow');
    });
});
