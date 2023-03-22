Python Dynamic Default Arguments
======
![Build wheel](https://github.com/inspiros/dynamic-default-args/actions/workflows/build_wheels.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/dynamic-default-args)
![GitHub](https://img.shields.io/github/license/inspiros/dynamic-default-args)

This package provide facilities to make default arguments of python's functions dynamic.

### Context

This code is extracted from another project of mine.
It solves a problem that was also mentioned in
this [stackoverflow thread](https://stackoverflow.com/questions/16960469/dynamic-default-arguments-in-python-functions).

It turns out that changing functions' default arguments in an elegant way is a lot harder than what we think.
The common approach is to define a function that retrieves the value of the _default_ argument stored somewhere:

```python
class _empty(type):
    pass  # placeholder


B = 'path/to/heaven'


def get_default_b():
    # method that
    return B


def foo(a, b=_empty):
    if b is _empty:
        b = get_default_b()
    send_to(a, destination=b)  # do something


def main():
    global B
    B = 'path/to/hell'
    foo('Putin')
```

The old standard way is ok, but we should be aware of numbers of function calls when there are many arguments to be made
dynamically default.
But the point is, it doesn't look nice.

This module's solution limits to a single wrapper function, which is `compile`d from string to minimize overheads on
runtime.

### Requirements

- Python 3

### Installation

[dynamic-default-args](https://pypi.org/project/dynamic-default-args/) is available on PyPI, this is a pure Python
package.

```bash
pip install dynamic-default-args
```

### Usage

This package provides two components:

- `named_default`: A object that has a name and contains a value.
  This is a singleton-like object, which means any initialization with the same name will return the first one with the
  same registered name.
- `dynamic_default_args`: A function decorator for substituting any given `named_default` with its value when function
  is called.

#### Creating a `named_default`:

There are 2 ways to initialize a `named_default`, either pass a pair of `named_default(name, value)` positional
arguments or use a single keyword argument `named_default(name=value)`.

```python
from dynamic_default_args import named_default

# method 1
x = named_default('x', 1)
# method 2
y = named_default(y=1)
```

It is not necessary to keep the reference of this object as you can always recover them when calling `named_default`
again with the same name.

```python
from dynamic_default_args import named_default

print(named_default('x').value)
named_default('x').value = 1e-3
```

#### Decorating function with `dynamic_default_args`:

Here is an example in [`example.py`](examples/example.py):

```python title=foo.py
from dynamic_default_args import dynamic_default_args, named_default


# Note that even non-dynamic default args can be formatted because
# both are saved for populating positional-only defaults args
@dynamic_default_args()
def foo(a0=named_default(a0=5),
        a1=3,
        /,
        a2=named_default(a2=slice(0, 3)),
        a3=-1,
        *a4,
        a5=None,
        a6=named_default(a6='python'),
        **a7):
    """
    A Foo function that has dynamic default arguments.

    Args:
        a0: Positional-only argument a0. Dynamically defaults to a0={a0}.
        a1: Positional-only argument a1. Defaults to {a1}.
        a2: Positional-or-keyword argument a2. Dynamically defaults to a2={a2}.
        a3: Positional-or-keyword argument a3. Defaults to {a3}
        *a4: Varargs a4.
        a5: Keyword-only argument a5. Defaults to {a5}.
        a6: Keyword-only argument a6. Dynamically defaults to {a6}.
        a7: Varkeywords a7.
    """
    print('Called with:', a0, a1, a2, a3, a4, a5, a6, a7)


# test output:
foo()
# Called with: 5 3 0.01 -1 () None python
```

Internally, the auto generated wrapper for this function will be:

```python
def wrapper(a0=a0_, a1=a1_, a2=a2_, a3=a3_, *a4, a5=a5_, a6=a6_, **a7):
    return func(a0.value, a1, a2.value, a3, *a4, a5, a6.value, **a7)
```

whose defaults `a0_, a1_, a2_, a3_, a5_, a6_` are those of `func`(`=foo`), but the contained `named_default`s will have
their values forwarded instead. The aliases `wrapper` and `func` are assured to be different from arguments' names.

By passing `format_doc=True` (which is the default behavior), the decorator will try to bind default values of argument
with names defined in format keys of the docstring.
Any modification to the dynamic default values will update the docstring with an event.

```python
named_default('a2').value = range(10)
named_default('a6').value = 'rust'
help(foo)
```

Output: _(even normal default arguments will be formatted)_

```
foo(a0=5, a1=3, /, a2=range(0, 10), a3=-1, *a4, a5=None, a6='rust', **a7)
    A Foo function that has dynamic default arguments.
    
    Args:
        a0: Positional-only argument a0. Dynamically defaults to a0=5.
        a1: Positional-only argument a1. Defaults to 3.
        a2: Positional-or-keyword argument a2. Dynamically defaults to a2=range(0, 10).
        a3: Positional-or-keyword argument a3. Defaults to -1
        *a4: Varargs a4.
        a5: Keyword-only argument a5. Defaults to None.
        a6: Keyword-only argument a6. Dynamically defaults to rust.
        a7: Varkeywords a7.
```

#### Binding

The `named_default` object will emit an event to all registered listeners, which can be set by calling `.connect`
method:

```python
from dynamic_default_args import named_default

variable = named_default('my_variable', None)


def on_variable_changed(value):
    print(f'Changed to {value}')


variable.connect(on_variable_changed)
```

### Limitations

This solution relies on function introspection provided by the `inspect` module, which does not work on built-in
functions (including C/C++ extensions).
However, you can wrap them with a python with, or modify the source code of the decorator to accept a custom signature
as argument.

For **Cython** users, a `def` or `cpdef` (might be inspected incorrectly) function defined in `.pyx` files can be
decorated by setting `binding=True`.

```cython
import cython

from dynamic_default_args import dynamic_default_args, named_default

@dynamic_default_args(format_doc=True)
@cython.binding(True)
def add(x: float = named_default(x=0.),
        y: float = named_default(y=0.)):
    """``cython.binding`` will add docstring to the wrapped function,
    so we can format it later.

        Args:
            x: First argument, dynamically defaults to {x}
            y: Second argument, dynamically defaults to {y}

        Returns:
            The sum of x and y
    """
    return x + y
```

Also, it is clear that decorators are not lazily initialized.

**Further improvements:**

Modifying the `func.__defaults__` should be more performant.

### License

The code is released under MIT-0 license. See [`LICENSE.txt`](LICENSE.txt) for details.
Feel free to do anything, I would be surprised if anyone does use this 😐.
