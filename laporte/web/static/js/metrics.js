/* global 
    io
*/

function refresh_metrics() {
    const url = '/metrics';
    $.get(url, function (data) {
        var lines = data.split("\n");
        $('#metrics').html("");

        for (var line in data.split("\n")) {
            if (lines[line].charAt(0) === "#") {
                $('#metrics').append('<span class="text-secondary">' + lines[line] + '</span><br/>');
            } else {
                $('#metrics').append(lines[line] + '<br/>');
            }
        }
    });
}

$(document).ready(function () {
    // Connect to the Socket.IO server.
    const namespace = "/events";
    const url = `${location.protocol}//${document.domain}:${location.port}`;
    var socket = io.connect(url + namespace);
    $('#url').html('<small><a href="' + url + '/metrics">' + url + '/metrics</a></small>');


    // Event handler for new connections.
    socket.on('connect', function () {
        $('#status').html("connected");
        refresh_metrics();
    });

    // Event handler for lost connection.
    socket.on('disconnect', function () {
        $('#status').html("not connected");
    });

    // Event handler for server sent event data.
    /* jshint unused: vars */
    socket.on('event_response', function (msg) {
        refresh_metrics();
    });
});