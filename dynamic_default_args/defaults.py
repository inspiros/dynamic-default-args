"""Shared values and factories used by the decorator."""
import inspect
from threading import RLock

from .event import Event

__all__ = ["default", "named_default", "default_factory"]
_MISSING = object()


class default(Event):
    """A shared default value. Assignment to ``value`` notifies listeners."""
    __slots__ = ("_value",)

    def __init__(self, value):
        super().__init__()
        self._value = value

    def __repr__(self):
        return repr(self._value)

    def __eq__(self, other):
        return self._value == (other._value if isinstance(other, default) else other)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value
        self.emit(value)

    def _resolve(self):
        return self._value


class _NamedDefaultMeta(type):
    _instances = {}
    _registry_lock = RLock()

    def __call__(cls, name=_MISSING, value=_MISSING, **kwargs):
        if kwargs:
            if len(kwargs) != 1 or name is not _MISSING or value is not _MISSING:
                raise ValueError("Use named_default(name, value), named_default(name=..., "
                                 "value=...), or named_default(key=value)")
            name, value = next(iter(kwargs.items()))
        if not isinstance(name, str):
            raise ValueError("A named default needs a string name")
        with cls._registry_lock:
            if name not in cls._instances:
                if value is _MISSING:
                    raise ValueError(f"{name} has not been registered.")
                cls._instances[name] = super().__call__(name, value)
            return cls._instances[name]


class named_default(default, metaclass=_NamedDefaultMeta):
    """A process-wide shared value, retrieved by name; first definition wins."""
    __slots__ = ("name",)

    def __init__(self, name, value):
        super().__init__(value)
        self.name = name

    @classmethod
    def unregister(cls, name):
        """Forget a registry entry. Existing references keep their value."""
        with cls._registry_lock:
            cls._instances.pop(name, None)


class default_factory:
    """Compute a value for each omitted argument.

    ``depends_on`` names earlier parameters passed positionally to the factory.
    Factories are synchronous, including for async functions.
    """
    __slots__ = ("factory", "depends_on")

    def __init__(self, factory, *, depends_on=()):
        if not callable(factory):
            raise TypeError("A default factory must be callable")
        if inspect.iscoroutinefunction(factory) or inspect.isasyncgenfunction(factory):
            raise TypeError("Default factories must be synchronous")
        if isinstance(depends_on, str):
            raise TypeError("depends_on must be a sequence of parameter names")
        dependencies = tuple(depends_on)
        if any(not isinstance(name, str) for name in dependencies):
            raise TypeError("depends_on must contain parameter names")
        self.factory = factory
        self.depends_on = dependencies

    def _resolve(self, *args):
        return self.factory(*args)

    def __repr__(self):
        name = getattr(self.factory, "__qualname__", type(self.factory).__name__)
        suffix = f", depends_on={self.depends_on!r}" if self.depends_on else ""
        return f"default_factory({name}{suffix})"
