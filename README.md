# Python Dynamic Default Arguments

[![Tests](https://github.com/inspiros/dynamic-default-args/actions/workflows/tests.yml/badge.svg)](https://github.com/inspiros/dynamic-default-args/actions/workflows/tests.yml)
[![Package](https://github.com/inspiros/dynamic-default-args/actions/workflows/package.yml/badge.svg)](https://github.com/inspiros/dynamic-default-args/actions/workflows/package.yml)
[![PyPI](https://img.shields.io/pypi/v/dynamic-default-args)](https://pypi.org/project/dynamic-default-args/)
[![Downloads](https://static.pepy.tech/badge/dynamic-default-args)](https://pepy.tech/project/dynamic-default-args)
[![License: MIT-0](https://img.shields.io/badge/license-MIT--0-blue.svg)](https://github.com/inspiros/dynamic-default-args/blob/master/LICENSE)

Shared defaults you can update, and factories evaluated for each omitted argument.
Pure Python, with no runtime dependencies.

Supports **Python 3.8–3.15** and **Cython 3**.

## Installation

From [PyPI](https://pypi.org/project/dynamic-default-args/):

```bash
python -m pip install dynamic-default-args
```

Or from a local checkout (Python 3.9+):

```bash
python -m pip install .
```

## Shared Defaults

```python
from dynamic_default_args import default, default_factory, dynamic_default_args

timeout = default(5)

@dynamic_default_args
def request(url, timeout=timeout):
    return url, timeout

assert request("/status") == ("/status", 5)
timeout.value = 10
assert request("/status") == ("/status", 10)
assert request("/status", None) == ("/status", None)
```

Only omitted arguments resolve. Explicit values, including `None`, pass through.
A `default` cell shares its value; use a factory when each call needs a fresh object.

Omitted static defaults stay with the wrapped callable. Place `@dynamic_default_args`
above a validation decorator (such as Pydantic's `@validate_call`) to validate dynamic
values while preserving static omissions. Static positional-only defaults
are forwarded only when needed to reach a later positional-only argument.

## Factories

`default_factory` computes a value per omission. Its optional `depends_on` names
earlier parameters, passed to the factory in the given order:

```python
@dynamic_default_args()
def take(items, limit=default_factory(len, depends_on=("items",)), *,
         output=default_factory(list)):
    output.extend(items[:limit])
    return output

assert take([1, 2, 3]) == [1, 2, 3]
assert take([1, 2, 3], 1) == [1]
```

Factories are synchronous and resolve from left to right. `default(callable)`
passes the callable itself; `default_factory(callable)` invokes it.
With an inner validator, factories receive dependency values before validation.

## Methods

Instance, class, and static methods, inheritance, and bound methods are supported.
Either decorator order works with `classmethod` and `staticmethod`.

```python
class Client:
    timeout = 5

    @dynamic_default_args
    def request(self, timeout=default_factory(lambda self: self.timeout,
                                              depends_on=("self",))):
        return timeout

client = Client()
assert client.request() == 5
client.timeout = 10
assert client.request() == 10
```

Class-method factories can similarly depend on `cls`.

## Named Defaults

Use `named_default` to retrieve a shared cell across modules:

```python
from dynamic_default_args import named_default

shared = named_default("myapp.timeout", 5)
assert named_default("myapp.timeout") is shared
named_default("myapp.timeout").value = 10
named_default.unregister("myapp.timeout")
```

The first registration wins; later initialization values are ignored.

## Defaults Outside the Signature

The `defaults` mapping is useful for typed functions and Cython parameters:

```python
scale = default(2.0)

@dynamic_default_args(defaults={"x": scale})
def compute(x: float = 0.0) -> float:
    return x * 2

assert compute() == 4.0
scale.value = 3.0
assert compute() == 6.0
```

For typed Cython parameters, keep valid native defaults and supply dynamic values
through this mapping. Python wrappers around `cpdef` are supported; C-level calls
retain native defaults. See [the Cython example](https://github.com/inspiros/dynamic-default-args/blob/master/examples/cython_defaults.pyx) and
its [build-and-run helper](https://github.com/inspiros/dynamic-default-args/blob/master/examples/build_cython.py).

## Other Features

- Preserves positional-only, keyword-only, and variadic argument binding.
- Supports partials, callable instances, and inspectable built-ins.
- Preserves coroutine, generator, and async-generator behavior. Defaults resolve
  when execution starts, or on first iteration for generators.
- `format_doc=True` updates simple docstring fields such as `{timeout}` when a
  shared value changes. Set it to `False` to leave docstrings unchanged.
- Shared cells expose `connect(callback)`, `disconnect(callback)`, and
  `disconnect_all()` for change notifications.
- `signature=inspect.Signature(...)` adapts callables without signature metadata;
  its static defaults are supplied explicitly to the target.

More runnable Python examples are in [examples/factories.py](https://github.com/inspiros/dynamic-default-args/blob/master/examples/factories.py).
See [CHANGELOG.md](https://github.com/inspiros/dynamic-default-args/blob/master/CHANGELOG.md) for changes. Licensed under [MIT-0](https://github.com/inspiros/dynamic-default-args/blob/master/LICENSE).
