var mobius_app = angular.module("mobius_app", [
    'ngRoute',
    'mobiusControllers'
]);

mobius_app.config(['$routeProvider',
    function($routeProvider) {
        $routeProvider.
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
