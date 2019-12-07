function refresh_metrics() {
    const url = '/metrics';
    $.get(url, function(data, status) {
        var lines = data.split("\n");
        $('#metrics').html("");

        for (line in data.split("\n")) {
            if (lines[line].charAt(0) == "#") {
                $('#metrics').append('<span class="text-secondary">' + lines[line] + '</span><br/>')
            } else {
                $('#metrics').append(lines[line] + '<br/>')
            }
        }
    })
}

$(document).ready(function() {
    const namespace = '/events';
    // Connect to the Socket.IO server.
    // The connection URL has the following format:
    //     http[s]://<domain>:<port>[/<namespace>]
    var url = location.protocol + '//' + document.domain + ':' + location.port 
    $('#url').html('<small><a href="' + url + '/metrics">' + url + '/metrics</a></small>');
    var socket = io.connect(url + namespace);


    // Event handler for new connections.
    socket.on('connect', function() {
        $('#status').html("connected");
        refresh_metrics();
    });

    socket.on('disconnect', function() {
        $('#status').html("not connected");
    });

    // Event handler for server sent event data.
    socket.on('update_response', function(msg) {
        refresh_metrics();
    });
});