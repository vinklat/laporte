var msg_id = 0;

$(document).ready(function() {
   namespace = '/events';
   // Connect to the Socket.IO server.
   // The connection URL has the following format:
   //     http[s]://<domain>:<port>[/<namespace>]
   var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port + namespace);

   // Event handler for new connections.
   socket.on('connect', function() {
        $('#status').html("connected");
   });

   socket.on('disconnect', function() {
        $('#status').html("not connected");
   });

   // Event handler for server sent event data.
   socket.on('update_response', function(msg) {
        var t = new Date().toLocaleTimeString(time_locale);
        var row = '<tr><td>' + msg_id + "</td><td>" + t + '</td><td>' + msg + '</td></tr>';
        $('#log').prepend(row);
       msg_id += 1;
   });
});