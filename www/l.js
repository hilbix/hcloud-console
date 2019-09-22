// RFB holds the API to connect and communicate with a VNC server
import RFB from './core/rfb.js';

let rfb;
let desktopName;

// When this function is called we have
// successfully connected to a server
function connectedToServer(e) {
    status("Connected to " + desktopName);
}

// This function is called when we are disconnected
function disconnectedFromServer(e) {
    if (e.detail.clean) {
        status("Disconnected");
    } else {
        status("Something went wrong, connection is closed");
    }
}

// When this function is called, the server requires credentials to authenticate
function credentialsAreRequired(e) {
    const password = prompt("Password Required:");
    rfb.sendCredentials({ password: password });
}

// When this function is called we have received a desktop name from the server
function updateDesktopName(e) { desktopName = e.detail.name; }

// Show a status text in the top bar
function status(text) { document.getElementById('status').textContent = text; }

function debug(text) { document.getElementById('uhu').textContent = text; }


function sendCtrlAltDel() { rfb.sendCtrlAltDel(); return false; }
document.getElementById('sendCtrlAltDelButton').onclick = sendCtrlAltDel;

// | | |         | | |
// | | | Connect | | |
// v v v         v v v

status("Connecting");

// Get the websocket URL used to connect
var url=window.location.search.substr(1);
var pw =window.location.hash.substr(1);

debug(url);

// Creating a new RFB object will start a new connection
rfb = new RFB(document.getElementById('screen'), url,
  {
    credentials: { password: pw },
    wsProtocols: [ 'binary' ],
  });

// Add listeners to important events from the RFB module
rfb.addEventListener("connect",  connectedToServer);
rfb.addEventListener("disconnect", disconnectedFromServer);
rfb.addEventListener("credentialsrequired", credentialsAreRequired);
rfb.addEventListener("desktopname", updateDesktopName);

// Set parameters that can be changed on an active connection
rfb.viewOnly = false;
rfb.scaleViewport = false;

