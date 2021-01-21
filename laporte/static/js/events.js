/* global 
    io, locale, followLogs, scrollToBottomAnimate
*/

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

    // Event handler for server sent event data.
    socket.on("update_response", function (msg) {
        var t = new Date().toLocaleTimeString(locale);
        var obj = JSON.parse(msg);
        var data = JSON.stringify(obj, null, 4);

        var row = `
          <tr>
               <td>
                    ${t}
               </td>
               <td>
               </td>
               <td>
                    ${data}
               </td>
          </tr>`;
        $("#log").append(row);

        if (followLogs()) {
            scrollToBottomAnimate();
        }
    });
});