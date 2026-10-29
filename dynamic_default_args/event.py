"""Small synchronous event dispatcher, with optional weak subscriptions."""
import inspect
from threading import RLock
from types import BuiltinMethodType, MethodType, MethodWrapperType, ModuleType
import weakref

__all__ = ["Event"]


def _is_bound_method(func):
    """Attribute access creates a new bound-method object each time."""
    return (isinstance(func, (MethodType, BuiltinMethodType, MethodWrapperType))
            and not isinstance(func.__self__, (ModuleType, type(None))))


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
        if weak and _is_bound_method(func) and not inspect.ismethod(func):
            # A weak reference to this temporary object would die immediately.
            raise TypeError("weak=True does not support built-in bound methods")
        reference = (weakref.WeakMethod(func) if inspect.ismethod(func)
                     else weakref.ref(func)) if weak else None
        with self._event_lock:
            self._prune()
            if not any(self._same_callback(self._callback(entry), func)
                       for entry in self._listeners):
                self._listeners.append((weak, reference if weak else func))

    @staticmethod
    def _callback(entry):
        weak, listener = entry
        return listener() if weak else listener

    @staticmethod
    def _same_callback(left, right):
        if left is right:
            return True
        if (type(left) is not type(right) or not _is_bound_method(left)
                or left.__self__ is not right.__self__):
            return False
        if inspect.ismethod(left):
            return left.__func__ is right.__func__
        return left.__name__ == right.__name__

    def _prune(self):
        self._listeners[:] = [entry for entry in self._listeners
                              if self._callback(entry) is not None]

    def disconnect(self, func):
        with self._event_lock:
            self._listeners[:] = [entry for entry in self._listeners
                                  if (callback := self._callback(entry)) is not None
                                  and not self._same_callback(callback, func)]

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
