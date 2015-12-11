import json


class Singleton(type):
    '''
    To create a singleton class use this class as a metaclass.
    '''
    _instance = None

    def __call__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instance


class JSONObject:
    '''
    This class allows a user to access json variables as if they were proper
    attributes.
    '''
    def __init__(self, json_string="{}"):
        self.__dict__ = json.loads(json_string)

    def __getitem__(self, prop):
        '''
        Implement getitem in terms of getattr.
        '''
        return getattr(self, prop)

    def __contains__(self, prop):
        return prop in self.__dict__

    def __setitem__(self, prop, value):
        '''
        Overriding setitem for easy item assignment on the _json_obj.

        @param prop - new property to set on the json object
        @param value - value of the new property
        '''
        setattr(self, prop, value)

    def __delitem__(self, prop):
        '''
        Allow easy deletion of properties.

        @param prop - property to be deleted from JSONObject
        '''
        del self.__dict__[prop]

    @property
    def json_string(self):
        '''
        Properly encoded representation of json object as string.
        '''
        return json.dumps(self.__dict__)

    def __repr__(self):
        return self.json_string
