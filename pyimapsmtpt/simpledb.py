# coding: utf8
""" ...

Similar to `shelve`, but with save on each write (or delayed) rather than on
close, with possible extras for atomicity (for consistency). Only writes the
whole data, can use user-specified serialization.
"""

try:
    import simplejson as json
except Exception:
    import json

import functools
import errno
import logging


from UserDict import UserDict


def _dumps_to_dump(dumps_func):

    @functools.wraps(dumps_func)
    def _wrapped_dump(val, fo, *ar, **kwa):
        data = dumps_func(val, *ar, **kwa)
        return fo.write(data)

    return _wrapped_dump


def _loads_to_load(loads_func):

    @functools.wraps(loads_func)
    def _wrapped_load(fo, *ar, **kwa):
        data = fo.read()
        return loads_func(data, *ar, **kwa)

    return _wrapped_load


def _save_wrapped(name):
    """ A helper-wrapper for SimpleDB that passes the call to self.dict and
    then calls self.save() """

    def _wrapped(self, *ar, **kwa):
        method = getattr(self.data, name)
        res = method(*ar, **kwa)
        self.save()
        return res

    _wrapped.__name__ = name
    return _wrapped


class SimpleDB(UserDict):
    """ A 'database' made from dict that loads the data from a file on init
    (if the file exists), and saves the data back when it is changed
    (instantly).  """

    # Flag to temporarily disable saving
    _nosave = False

    def __init__(self, filename, _ser=None, _load=True, _open_cm=None):
        UserDict.__init__(self)  # Just to honour it
        if _ser is None:
            _ser = {'dump': json.dump, 'load': json.load}
        # Allow specifying dumps/loads instead of dump/load
        if 'dump' not in _ser:
            _ser = dict(_ser, dump=_dumps_to_dump(_ser['dumps']))
        if 'load' not in _ser:
            _ser = dict(_ser, dump=_loads_to_load(_ser['loads']))
        # ...
        self._ser = _ser
        # Prefer AtomicFile for writing if available.
        if _open_cm is None:
            try:
                from atomicfile import AtomicFile
            except Exception:
                # Alas, nope
                _open_cm = open
            else:
                _open_cm = AtomicFile
        self._open_cm = _open_cm
        # ...
        self._filename = filename
        data = {}
        if _load:
            data = self.try_load() or data
        self.data = data

    def try_load(self):
        """ Attempt to self.load, return None if it raises 'file not found' """
        try:
            return self.load()
        except (IOError, OSError) as exc:
            if exc.errno != errno.ENOENT:
                raise
            return None

    def load(self):
        with open(self._filename, 'rb') as fo:
            return self._ser['load'](fo)

    __setitem__ = _save_wrapped('__setitem__')
    __delitem__ = _save_wrapped('__delitem__')
    pop = _save_wrapped('pop')
    popitem = _save_wrapped('popitem')
    update = _save_wrapped('update')

    def setdefault(self, key, failobj=None):
        try:
            return self[key]
        except KeyError:
            self[key] = failobj
            return failobj

    # Bonus functions: lazy get and setdefault

    def fsetdefault(self, key, failfunc=lambda: None):
        try:
            return self[key]
        except KeyError:
            val = failfunc()
            self[key] = val
            return val

    def fget(self, key, failfunc=lambda: None):
        try:
            return self[key]
        except KeyError:
            return failfunc()

    def subdict(self, key):
        """
        A complicated helper.
        As it is not called automatically, after loading the db you *might*
        have to call this for each key with a dict where you want to have the
        key changes saved.
        """
        val = Subdict(self.get(key) or {}, parent=self)
        self[key] = val
        return val

    # Some things that should not be done

    def copy(self):
        raise Exception("Bad idea")

    @classmethod
    def fromkeys(cls, *ar, **kwa):
        raise Exception("Bad idea")

    def save(self):
        if self._nosave:
            return
        self.sync()

    def sync(self):
        """ ...

        Separated from save() for easier overridability. """
        with self._open_cm(self._filename, 'wb') as fo:
            return self._ser['dump'](self.data, fo)


def _child_wrapped(name):
    """ A helper-wrapper for Subdict: passes the call to dict(self, ...)
    and then calls self.save() """

    def _wrapped(self, *ar, **kwa):
        method = getattr(dict, name)
        res = method(self, *ar, **kwa)
        self.save()
        return res

    _wrapped.__name__ = name
    return _wrapped


# This has to be a dict subclass (rather than UserDict) to be
# JSON-serializable.  Note that using it is likely tricky.
class Subdict(dict):
    """ Another dict subclass that can call parent.save() on write.
    Honours the '_nosave' attribute.

    Example use:
    >>> filename = '/tmp/._simpledb_subdict_test.json'
    >>> db = SimpleDB(filename)
    >>> key = 'child'
    >>> import random
    >>> val = random.getrandbits(31)
    >>> # Same as db.subdict(key)
    >>> db[key] = Subdict(db.get(key) or {}, parent=db)
    >>> db[key]['something'] = val
    >>> db2 = SimpleDB(filename)
    >>> assert db2[key]['something'] == val
    """

    _nosave = False

    def __init__(self, child=None, parent=None, **kwargs):
        self._parent = parent
        dict.__init__(self, child or {}, **kwargs)

    __setitem__ = _child_wrapped('__setitem__')
    __delitem__ = _child_wrapped('__delitem__')
    pop = _child_wrapped('pop')
    popitem = _child_wrapped('popitem')
    update = _child_wrapped('update')

    def save(self):
        if self._nosave:
            return

        if self._parent is not None:
            self._parent.save()


class SimpleDBDelayed(SimpleDB):
    """ A version of SimpleDB that uses gevent to save a few seconds after the
    first unsaved write. Requires the whole program to do wait on gevent often
    enough. """
    _save_delay = 5.001
    _save_waiter = None
    _nosave_delayed = False

    def _log(self, *ar, **kwa):
        level = kwa.pop("level", logging.INFO)
        logging.getLogger(self.__class__.__name__).log(level, *ar, **kwa)

    def save(self):
        if self._nosave:
            return  # Honour the _nosave anyway
        if self._save_waiter is None:
            import gevent
            self._log("Starting the waiter")
            self._save_waiter = gevent.Greenlet(self.save_actual)
            self._save_waiter.start_later(self._save_delay)
        else:
            self._log("Waiter was already started", level=2)

    def save_actual(self):
        self._log("save_actual()")
        if self._nosave_delayed:
            return
        try:
            self._log("sync()")
            self.sync()
            self._log("sync() done")
        finally:
            self._save_waiter = None
