'use strict';

var mobius_controls = angular.module("mobiusControllers", []);

mobius_controls.controller("PhoneListCtrl", ["$scope", "Phone",
    function($scope, Phone)
    {
        $scope.phones = Phone.query();
        $scope.order_prop = "age";
    }]);

mobius_controls.controller("PhoneDetailCtrl", ["$scope", "$routeParams", "Phone",
    function($scope, $routeParams, Phone)
    {
        $scope.phone = Phone.get({phone_id: $routeParams.phone_id}, function(phone) {
            $scope.mainImageUrl = phone.images[0];
        });

        $scope.setImage = function(imageUrl) {
            $scope.mainImageUrl = imageUrl;
        };
    }]);
