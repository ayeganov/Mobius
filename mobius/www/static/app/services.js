var mobiusServices = angular.module("mobiusServices", ['ngResource']);

mobiusServices.factory("Phone", ["$resource",
    function($resource){
        return $resource('static/phones/:phone_id.json', {}, {
            query: {method: 'GET', params: {phone_id: 'phones'}, isArray: true}
        });
    }]);


/**
 * This service gives access to the providers services on the backend. Requests
 * to handle file uploads to printer providers, quotes etc. should use this
 * service.
 */
mobiusServices.service("Providers", ["$q", "$rootScope", "SOCKET_ADDRESS",
    // Provider dependencies
    function($q, $rootScope, SOCKET_ADDRESS) {

        // This function will be instantiated with "new"
        return function(ws_url, on_recv)
        {
            var self = this;

            var callbacks = [];
            var request_queue = [];

            self.send_request = function(request) {
                if(self._web_sock.readyState !== 1)
                {
                    request_queue.push(request);
                }
                else
                {
                    self._web_sock.send(JSON.stringify(request));
                }
            };

            /**
             * This event fires when the socket is ready to send and receive.
             * In case users tried sending data before socket was ready this
             * function picks up all the events to be sent, and fires them off
             * in one go.
             */
            function sock_open(event) {
                _.each(request_queue, function(request) {
                    self._web_sock.send(JSON.stringify(request));
                });
                // empty the requests queue
                request_queue.length = 0;
            };

            /**
             * Handler of messages being received on this socket.
             *
             * @param message - message coming from the server
             */
            function sock_message(message) {
                var response = JSON.parse(message.data);
                _.each(callbacks, function(cb) {
                    $rootScope.$apply(function(){ cb(response); });
                });
            };

            function sock_close(event) {
                console.log("Web socket " + self.sock_url() + " is closed.");
            }

            function init()
            {
                self.sock_url = function() { return ws_url; };
                self._web_sock = new WebSocket(SOCKET_ADDRESS + ws_url);
                self._web_sock.onopen = sock_open;
                self._web_sock.onmessage = sock_message;
                if(on_recv)
                {
                    callbacks.push(on_recv);
                }
            }

            init();
        }
    }]);
