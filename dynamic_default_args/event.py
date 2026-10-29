"""Small synchronous event dispatcher, with optional weak subscriptions."""
import inspect
from threading import RLock
import weakref

__all__ = ["Event"]


class Event:
    __slots__ = ("_listeners", "_event_lock")

    def __init__(self):
        self._listeners = []
        self._event_lock = RLock()

    @property
    def on(self):
        def decorator(func):
            self.connect(func)
            return func
        return decorator

    def connect(self, func, *, weak=False):
        if not callable(func):
            raise TypeError("An event listener must be callable")
        reference = (weakref.WeakMethod(func) if inspect.ismethod(func)
                     else weakref.ref(func)) if weak else None
        with self._event_lock:
            self._prune()
            if not any(self._callback(entry) == func for entry in self._listeners):
                self._listeners.append((weak, reference if weak else func))

    @staticmethod
    def _callback(entry):
        weak, listener = entry
        return listener() if weak else listener

    def _prune(self):
        self._listeners[:] = [entry for entry in self._listeners
                              if self._callback(entry) is not None]

    def disconnect(self, func):
        with self._event_lock:
            self._listeners[:] = [entry for entry in self._listeners
                                  if self._callback(entry) not in (None, func)]

    def disconnect_all(self):
        with self._event_lock:
            self._listeners.clear()

    def emit(self, *args, **kwargs):
        with self._event_lock:
            self._prune()
            callbacks = [self._callback(entry) for entry in self._listeners]
        for callback in callbacks:
            if callback is not None:
                callback(*args, **kwargs)
