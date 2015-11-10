define([
    "utils/common",
    "dojox/widget/Toaster",
    "dijit/registry",
    "dojo/domReady!"
],
function(common, toaster, registry)
{
    function Stream(url)
    {
        // lets remember the handle to THIS object.
        var self = this;

        /**
         * Default message handling function
         */
        self._on_message = function(event) {
            _.each(self._handlers, function(handle) {
                handle(decodeURIComponent(event.data));
            });
        };

        self._on_error = function() {
            console.log("Showing fancy error message.");
        };

        self.register = function(callback) {
            self._handlers.push(callback);
        };

        self.write = function(message) {
            self._ws.send(message);
        };

        self.close = function() {
            self._ws.onclose = function() {};
            self._ws.close();
        };

        self.unregister = function(callback) {
            self._handlers = _.without(self._handlers, callback);
        };

        var init = function() {
            self._url = url;
            console.log("Connecting to " + common.SOCKET_ADDRESS + self._url);
            self._ws = new WebSocket(common.SOCKET_ADDRESS + self._url);
            self._ws.onmessage = self._on_message;
            self._ws.onerror = self._on_error;
            self._handlers = [];
        };

        init();
    };

    return {
        Stream: Stream
    };
});
