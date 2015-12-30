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


mobius_controls.controller("TestControl", ["$scope", "Providers",
    function($scope, Providers)
    {
        var msg_handler = function msg_handler(response)
        {
            $scope.test_var = response.apples;
        };
        var provider_request = new Providers("provider_request", msg_handler);

        $scope.send_request = function()
        {
            var request = {
                command: 1,
                message: "I got apples."
            };
            provider_request.send_request(request);
        };
    }]);


mobius_controls.controller('UploadFormCtrl',
    ['$scope', "$rootScope", 'Upload', '$timeout', "$uibModal", "$location", "Flash",
    function ($scope, $rootScope, Upload, $timeout, $uibModal, $location, Flash) {
        $scope.filename_error = "";
        $scope.show_filename_error = false;
        $scope.object_file_error = "";
        $scope.show_object_error = false;
        var max_file_size = 60 * 1024 * 1024;
        $scope.unit = "mm";


        $scope.validate_filename = function validate_filename(evt) {
            var show_tooltip = false;
            if(!_.isUndefined($scope.upload_form.fileName.$error.required))
            {
                $scope.filename_error = "File name is required."
                show_tooltip = true;
            }
            else if(!_.isUndefined($scope.upload_form.fileName.$error.minlength))
            {
                $scope.filename_error = "File name is too short."
                show_tooltip = true;
            }
            else if(!_.isUndefined($scope.upload_form.fileName.$error.maxlength))
            {
                $scope.filename_error = "File name is too long."
                show_tooltip = true;
            }

            $timeout(function() {
                $scope.show_filename_error = show_tooltip;
            });
        };

        $scope.validate_file = function validate_object_file() {
            if(_.isUndefined($scope.object_file)) return;

            var file_size = $scope.object_file.size;
            $scope.object_file_error = "";
            var show_tooltip = false;

            if(!_.isUndefined(file_size) && file_size > max_file_size)
            {
                $scope.object_file_error =
                    "File is too large. Max: " + ((max_file_size / 1024) / 1024) + "MB";
                show_tooltip = true;
            }

            $timeout(function() {
                $scope.show_object_error = show_tooltip;
            });
        };

        $scope.uploadFile = function(file) {
            file.upload = Upload.upload({
                url: '/upload',
                data: {fileID: file, fileName: $scope.filename},
            });

            file.upload.then(function success(response) {
                $location.path("/compare");
            }, function error(response) {
                Flash.create('danger', "<strong>Oh, snap</strong>, something went wrong on the server.");
            }, function progress(evt) {
                // Math.min is to fix IE which reports 200% sometimes
                var percent = Math.min(100, parseInt(100.0 * evt.loaded / evt.total));
                $rootScope.$broadcast("progress", percent);
            });
            open_modal();
        }

        var open_modal = function() {
            var modal_instance = $uibModal.open({
                animation: true,
                templateUrl: "upload_modal.html",
                controller: "UploadModalCtrl",
                size: "lg",
                backdrop: "static",
                keyboard: false
            });
        };

        $scope.show_message = function(){
            Flash.create("danger", "Danga danga!");
        };

    }]);


mobius_controls.controller('UploadModalCtrl', ['$scope', "$uibModalInstance", "$location", "$timeout",
    function($scope, $uibModalInstance, $location, $timeout) {

        $scope.progress = 0;

        $scope.$on("progress", function(event, percent) {
            $scope.progress = percent;

            if(percent >= 100)
            {
                $uibModalInstance.close();
            }
        });

        $scope.ok = function() {
            $uibModalInstance.close("ferriss blabla");
        };

        $scope.cancel = function() {
            $uibModalInstance.dismiss("cancel");
        };
    }]);
