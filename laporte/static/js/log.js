/* global 
    io, locale, followLogs, scrollToBottomAnimate, is_same_day,
    logTrClass, htmlEncode, checkTruncated, scrollToBottomInstant
*/

function print_log(log) {
    const { time, levelname, msg, request_id, funcname, filename, fileno } = log;
    const tlog = new Date(time * 1000);
    const tnow = new Date();

    var tstr = `${tlog.toLocaleTimeString(locale)}`;
    if (!is_same_day(tlog, tnow)) {
        tstr = `${tlog.toLocaleDateString(locale).replace(/ /g, '')} ` + tstr;
    }

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
                <small>${request_id}</small>
            </td>
            <td>
                ${funcname}
                <br/>
                <small class="text-secondary font-weight-light">
                    (${filename}:${fileno})
                </small>
            </td>
            <td class="small text-break">
                <div class="truncate-overflow">
                    <samp id="eval-truncate">${encodedMsg} </samp>
                </div>
            </td> 
        </tr>
    `;

    $('#log').append(row);

    //check if truncated
    const elem = $('#eval-truncate');
    checkTruncated(elem);
    elem.removeAttr('id');
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
    socket.on('init_response', function (msg) {
        var buf = JSON.parse(msg);

        $('#log').html('');
        buf.forEach(function (log) {
            print_log(log);
        });

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

    //toggle truncated
    $('#log').on('click', 'tr td div.long', function () {
        $(this).toggleClass('truncate-overflow');
    });

    $(window).resize(function () {
        $("#log tr td div samp").each(function () {
            checkTruncated(this);
        });
    });
});
