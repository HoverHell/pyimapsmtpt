# coding: utf8


def to_bytes(val):
    if isinstance(val, unicode):
        return val.encode('utf-8')
    return val
