# Python Dynamic Default Arguments

Shared defaults you can update, and factories evaluated for each omitted argument.
Pure Python, no runtime dependencies. Requires Python 3.10+.

```python
from dynamic_default_args import default, default_factory, dynamic_default_args

timeout = default(5)

@dynamic_default_args
def request(url, timeout=timeout, *, headers=default_factory(dict)):
    return url, timeout, headers

request("/status")            # ('/status', 5, {})
timeout.value = 10
request("/status")            # ('/status', 10, {}), a fresh dictionary
request("/status", None)      # Explicit None stays None
```

```bash
pip install dynamic-default-args
```

Supports positional-only and keyword-only parameters, methods, coroutines,
generators, async generators, and Python-facing Cython functions. Typed Cython
parameters use decorator-supplied defaults; see the compatibility guide.

- [Overview and design assessment](docs/overview.md)
- [API, semantics, and migration](docs/api.md)
- [Cython compatibility](docs/cython.md)
- [Development and releases](docs/development.md)
- [Changelog](docs/changelog.md)
- [Runnable examples](examples/)

Python still evaluates ordinary defaults at definition time. [PEP 671](https://peps.python.org/pep-0671/)
proposes native late-bound defaults and remains a draft. This library uses ordinary
Python decorators and explicit dependencies; it does not implement the proposed syntax.

Released under the [MIT-0 license](LICENSE.txt).
