# -*- coding: utf-8 -*-
'''
Store http request ID in flask's G object
'''

import uuid
from flask import g
from flask import _app_ctx_stack as stack

_G_ATTR_HTTP_REQUEST_ID = 'request_id'


class RequestID():
    @staticmethod
    def set(rid=None):
        '''
        Save http request ID into flask's G object.
        '''

        if rid is None:
            rid = str(uuid.uuid4())

        setattr(g, _G_ATTR_HTTP_REQUEST_ID, rid)

    @staticmethod
    def get():
        '''
        Get http request ID from flask's G object.
        '''

        if stack.top is not None:
            return g.get(_G_ATTR_HTTP_REQUEST_ID, None)

        return None
