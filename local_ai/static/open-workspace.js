// A file URL cannot load the server-root assets or authenticated API.
// This relative path also resolves to /static/ when served by the gateway.
if (window.location.protocol === "file:") {
  window.location.replace("http://127.0.0.1:9000/");
}
