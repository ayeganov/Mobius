var mobius_app = angular.module("mobius_app", [
    'ngRoute',
    'ngFileUpload',
    'ui.bootstrap',
    'flash',
    'mobiusAnimations',
    'mobiusControllers',
    'mobiusFilters',
    'mobiusServices'
]);

mobius_app.constant("WEB_ADDRESS", "http://" + document.location.hostname + ":8888/");
mobius_app.constant("SOCKET_ADDRESS", "ws://" + document.location.hostname + ":8888/ws/");

mobius_app.config(['$routeProvider',
    function($routeProvider) {
        $routeProvider.
            when("/", {
                templateUrl: '/static/partials/upload_form.html',
            }).
            when("/compare", {
                templateUrl: '/static/partials/compare.html',
            }).
            when("/phones", {
                templateUrl: '/static/partials/phone-list.html',
                controller: 'PhoneListCtrl'
            }).
            when("/phones/:phone_id", {
                templateUrl: '/static/partials/phone-detail.html',
                controller: 'PhoneDetailCtrl'
            }).
            otherwise({
                redirectTo: '/phones'
            });
    }]);
