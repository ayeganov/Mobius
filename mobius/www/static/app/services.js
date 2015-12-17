var mobiusServices = angular.module("mobiusServices", ['ngResource']);

mobiusServices.factory("Phone", ["$resource",
    function($resource){
        return $resource('static/phones/:phone_id.json', {}, {
            query: {method: 'GET', params: {phone_id: 'phones'}, isArray: true}
        });
    }]);
