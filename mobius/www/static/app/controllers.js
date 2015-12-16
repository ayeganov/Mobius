'use strict';

var mobius_controls = angular.module("mobiusControllers", []);

mobius_controls.controller("PhoneListCtrl", ["$scope", "$http",
    function($scope, $http)
    {
        $http.get("static/phones/phones.json").success(function(data)
        {
            $scope.phones = data;
        });

        $scope.order_prop = "age";
    }]);

mobius_controls.controller("PhoneDetailCtrl", ["$scope", "$routeParams", "$http",
    function($scope, $routeParams, $http)
    {
        $http.get("static/phones/" + $routeParams.phone_id + ".json").success(function(data)
        {
            $scope.phone = data;
        });
    }]);
