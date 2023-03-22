import array
import inspect
import string
from functools import wraps
from types import FunctionType
from typing import Optional, Any

import numpy as np

from .event import Event
from .format_dict import format_dict
from .setter_property import SetterProperty

__all__ = [
    'default',
    'named_default',
    'dynamic_default_args',
]

_empty = __import__('inspect')._empty


class _default(Event):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def __repr__(self):
        return repr(self.value)

    @SetterProperty
    def value(self, value):
        self.__dict__['value'] = value
        self.emit(value)


class _NamedDefaultMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if len(args) == 2 and args[0] is None:
            args = ()
        from_args = len(args) in (1, 2)
        from_kwargs = len(kwargs) == 1
        if not from_args ^ from_kwargs:
            raise ValueError('Define named default with one string and one value, '
                             'either by two positional arguments or a single keyword '
                             'argument. If only name given, value will be set to None.')
        if from_args:
            name, value = args[0], args[1] if len(args) == 2 else None
        elif from_kwargs:
            name, value = next(iter(kwargs.items()))
        if not isinstance(name, str):
            raise ValueError(f'Name must be string. Got {type(name)}.')
        if name not in cls._instances:
            cls._instances[name] = super(_NamedDefaultMeta, cls).__call__(name, value)
        return cls._instances[name]


class _named_default(_default, metaclass=_NamedDefaultMeta):
    def __init__(self, name=None, value=None, **kwargs):
        super().__init__(value)
        self.name = name


def default(value: Any) -> Any:
    """
    Create a default object that holds a default value.
    """
    return _default(value)


def named_default(name: Optional[str] = None,
                  value: Optional[Any] = None,
                  **kwargs) -> Any:
    """Create a named default object that holds a default value
    for arguments, which can be dynamically changed later.

    This function accpets passing two positional arguments name
    and value. If value is not provided and the name hasn't been
    registered, value will be set to ``None``.

    >>> def foo(x=named_default('x', 0.5)):
    >>>    ...

    Ortherwise, use a single keyword argument. The keyword will
    be used as name.

    >>> def foo(x=named_default(x=1)):
    >>>    ...

    For modifying the default values everywhere, call this function
    with only the name of defined variable. Any value provided will
    have no effect.

    >>> default_x = named_default('x')
    >>> default_x.value = 2.0
    """
    return _named_default(name, value, **kwargs)


class _DynamicDefaultWrapperFactory:
    # container for compiled wrappers
    _COMPILED_WRAPPERS = {}

    @classmethod
    def get_compiled_wrapper(cls,
                             has_pso_dd=False,
                             has_psokw_dd=False,
                             has_kwo_dd=False):
        key = (has_pso_dd, has_psokw_dd, has_kwo_dd)
        if key not in cls._COMPILED_WRAPPERS:
            expr = """\
def wrapper(*args, **kwargs):"""
            if has_pso_dd or has_psokw_dd:
                expr += """
    n_args = len(args)"""
            if has_pso_dd:
                expr += """
    extra_args = [None] * (pso_dd_inds[-1] + 1 - n_args)"""
            if has_psokw_dd:
                expr += """
    psokw_dd_keys = array('i')"""
            if has_pso_dd:
                expr += """
    if len(extra_args):
        for i in range(n_args, pso_dd_inds[-1] + 1):
            if default_mask[i]:
                extra_args[i - n_args] = defaults[i].value
            else: break"""
            if has_psokw_dd:
                expr += """
    for i in psokw_dd_inds:
        if i >= n_args:
            psokw_dd_keys.append(i)
    for i in psokw_dd_keys:
        param_name = names[i]
        if param_name not in kwargs:
            kwargs[param_name] = defaults[i].value"""
            if has_kwo_dd:
                expr += """
    for i in kwo_dd_inds:
        param_name = names[i]
        if param_name not in kwargs:
            kwargs[param_name] = defaults[i].value"""
            expr += """
    return func(*args, {}**kwargs)""".format('*extra_args, ' if has_pso_dd else '')

            cls._COMPILED_WRAPPERS[key] = compile(expr, f'<dynamic_default_function_wrapper>', 'exec')
        return cls._COMPILED_WRAPPERS[key]


def dynamic_default_args(format_doc=True, force_wrap=False):
    """
    A decorator for substituting function with dynamic default
    arguments with minimal overhead.

    It can also will modify the function's docstring with
    format keys automatically when any of the default args changes.

    >>> @dynamic_default_args(format_doc=True)
    >>> def foo(x=named_default(x=5))
    >>>     \"\"\"An exmaple function with docstring.
    >>>
    >>>     Args:
    >>>         x: Argument dynamically defaults to {x}.
    >>>     \"\"\"
    >>>     print(x)

    When the default value is changed later, both the default and
    the function's docstring will be updated accordingly.

    >>> named_default('x').value = 10
    >>> foo()
    10
    >>> help(foo)

    Args:
        format_doc: Automatically format the docstring of the
         decorated function or not. Defaults to ``True``.
        force_wrap: Wrap the decorated function even if there
         is no dynamic default argument or not.
         Defaults to ``False``.
    """
    def decorator(func):
        params = inspect.signature(func).parameters
        n_params = len(params)

        names = [None] * n_params
        defaults = [None] * n_params
        kinds = np.empty(n_params, dtype=np.int64)
        default_mask = np.zeros(n_params, dtype=np.bool_)
        dynamic_default_mask = np.zeros(n_params, dtype=np.bool_)

        for i, (k, v) in enumerate(params.items()):
            names[i] = k
            kinds[i] = v.kind
            default_mask[i] = v.default is not _empty
            dynamic_default_mask[i] = isinstance(v.default, _default)
            defaults[i] = v.default if dynamic_default_mask[i] else _default(v.default)

        pso_mask = kinds == 0  # POSITIONAL_ONLY
        psokw_mask = kinds == 1  # POSITIONAL_OR_KEYWORD
        var_mask = kinds == 2  # VAR_POSITIONAL
        kwo_mask = kinds == 3  # KEYWORD_ONLY

        pso_start, psokw_start, var_start, kwo_start, _ = np.cumsum(np.pad(
            np.stack([pso_mask, psokw_mask, var_mask, kwo_mask]).sum(1), [(1, 0)]))

        pso_dd_inds, psokw_dd_inds, kwo_dd_inds = \
            [np.where(type_mask * dynamic_default_mask)[0]
             for type_mask in [pso_mask, psokw_mask, kwo_mask]]

        if pso_dd_inds.size + psokw_dd_inds.size + kwo_dd_inds.size or force_wrap:
            compiled_wrapper = _DynamicDefaultWrapperFactory.get_compiled_wrapper(
                pso_dd_inds.size > 0, psokw_dd_inds.size > 0, kwo_dd_inds.size > 0)
            wrapper = wraps(func)(
                FunctionType(compiled_wrapper.co_consts[0], globals=dict(
                    len=len,
                    range=range,
                    array=array.array,
                    func=func,
                    names=names,
                    defaults=defaults,
                    default_mask=default_mask,
                    psokw_start=psokw_start,
                    pso_dd_inds=pso_dd_inds,
                    psokw_dd_inds=psokw_dd_inds,
                    kwo_dd_inds=kwo_dd_inds,
                )))
        else:  # no wrapping
            wrapper = func

        if format_doc and wrapper.__doc__ is not None:
            format_keys = set(_[1] for _ in string.Formatter().parse(wrapper.__doc__)
                              if _[1] is not None)
            if len(format_keys.intersection(names)):
                # format docstring
                wrapper.__default_doc__ = wrapper.__doc__
                format_keys_ids = [i for i in range(n_params)
                                   if names[i] in format_keys]

                def update_docstring(*args, **kwargs):
                    wrapper.__doc__ = wrapper.__default_doc__.format_map(format_dict(
                        {names[i]: defaults[i].value for i in format_keys_ids}))

                update_docstring()
                # automatic update later
                for i in format_keys_ids:
                    defaults[i].connect(update_docstring)

        return wrapper

    return decorator
