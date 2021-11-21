# -*- coding: utf-8 -*-
'''
Store event ID of sensor update in flask's G object
'''

from flask import g
from flask import _app_ctx_stack as stack

_G_ATTR_EVENT_ID = 'event_id'


class EventID():
    def __init__(self):
        self.event_cnt = 0

    def set(self, add_prefix="", add_suffix="", eid=None):
        '''
        Save event ID into flask's G object.
        '''

        if eid is None:
            self.event_cnt += 1
            eid = f'{self.event_cnt:06x}'

        setattr(g, _G_ATTR_EVENT_ID, add_prefix + eid + add_suffix)

    @staticmethod
    def get():
        '''
        Get event ID from flask's G object.
        '''

        if stack.top is not None:
            return g.get(_G_ATTR_EVENT_ID, None)

        return None

    @staticmethod
    def release():
        '''
        Remove event ID from flask's G object.
        '''

        if stack.top is not None:
            delattr(g, _G_ATTR_EVENT_ID)
