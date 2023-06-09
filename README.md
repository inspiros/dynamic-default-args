Python Dynamic Default Arguments
======
![Build wheel](https://github.com/inspiros/dynamic-default-args/actions/workflows/build_wheels.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/dynamic-default-args)
![GitHub](https://img.shields.io/github/license/inspiros/dynamic-default-args)

This package provides facilities to make default arguments of Python's functions dynamic (in an elegant manner).

## Context

The package solves a problem that was also mentioned in
this [stackoverflow thread](https://stackoverflow.com/questions/16960469/dynamic-default-arguments-in-python-functions).

The common approach is to define a function that retrieves the value of the _default_ argument stored somewhere:

```python
class _empty(type):
    pass  # placeholder


B = 'path/to/heaven'


def get_default_b():
    # function that retrieves the 'default' value
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

## Requirements

- Python 3

## Installation

[dynamic-default-args](https://pypi.org/project/dynamic-default-args/) is available on PyPI, this is a pure Python
package.

```bash
pip install dynamic-default-args
```

## Usage

This package provides two components:

- `named_default`: A object that has a name and contains a value.
  This is a singleton-like object, which means any initialization with the same name will return the first one with the
  same registered name.
- `dynamic_default_args`: A function decorator for substituting any given `named_default` with its value when function
  is called.

### Creating a `named_default`:

There are 3 ways to initialize a `named_default`:

- Pass a pair of positional arguments `named_default([name], [value])`
- Pass the two keywords `named_default(name=[name], value=[value])`
- Pass a single keyword argument `named_default([name]=[value])`.

```python
from dynamic_default_args import named_default

# method 1
x = named_default('x', 1)
# method 2
y = named_default(name='y', value=2)
# method 3
z = named_default(z=3)
```

It is not necessary to keep the reference of this object as you can always recover them when calling `named_default`
again with the same name. New value passed to the constructor will be ignored.

```python
from dynamic_default_args import named_default

print(named_default('x').value)
named_default('x').value = 1e-3
```

Trying to access an unregistered name will raise Exception.

```python
from dynamic_default_args import named_default

print(named_default('an_unregistered_name').value)
# ValueError: an_unregistered_name has not been registered.
```

### Decorating functions with `dynamic_default_args`:

Here is an example in [`example.py`](examples/example.py) on Python 3.8+:

```python title=foo.py
from dynamic_default_args import dynamic_default_args, named_default


# Note that even non-dynamic default args can be formatted because
# both are saved for populating positional-only defaults args
@dynamic_default_args(format_doc=True)
def foo(a0,
        a1=named_default(a1=5),
        a2=3,
        /,
        a3=named_default(a3=slice(0, 3)),
        a4=-1,
        *a5,
        a6=None,
        a7=named_default(a7='python'),
        **a8):
    """
    A Foo function that has dynamic default arguments.

    Args:
        a0: Required Positional-only argument a0.
        a1: Positional-only argument a1. Dynamically defaults to a0={a1}.
        a2: Positional-only argument a1. Defaults to {a2}.
        a3: Positional-or-keyword argument a2. Dynamically defaults to a3={a3}.
        a4: Positional-or-keyword argument a4. Defaults to {a4}
        *a5: Varargs a5.
        a6: Keyword-only argument a5. Defaults to {a6}.
        a7: Keyword-only argument a6. Dynamically defaults to {a7}.
        **a8: Varkeywords a8.
    """
    print(f'Called with: a0={a0}, a1={a1}, a2={a2}, a3={a3}, '
          f'a4={a4}, a5={a5}, a6={a6}, a7={a7}, a8={a8}')


# test output:
foo(0)
# Called with: a0=0, a1=5, a2=3, a3=slice(0, 3, None), a4=-1, a5=(), a6=None, a7=python, a8={}
```

#### How it works?

Internally, the auto generated wrapper with similar signature for this function will be (without formatting):

```python
def wrapper(a0, a1=a1_, a2=a2_, a3=a3_, a4=a4_, *a5, a6=a6_, a7=a7_, **a8):
    func(a0,
         a1._value if isinstance(a1, default) else a1,
         a2,
         a3._value if isinstance(a3, default) else a3,
         a4,
         *a5,
         a6=a6,
         a7=a7._value if isinstance(a7, default) else a7,
         **a8)
```

whose defaults are set to those of `func`(`=foo`), but the contained `named_default`s will be type checked and have
their values forwarded instead.
How the arguments are forwared depend on the type of arguments:

- **Positional-only**: with its name, e.g.`a0`, `a1`, `a2`
- **Keyword-or-position**: with its name, e.g. `a3`, `a4`
- **Varargs**: with an asterisk operator, e.g. `*a5`
- **Keyword-only**: with its name as key, e.g. `a6=a6`, `a7=a7`
- **Varkeywords**: with double asterick operator, e.g. `**a8`

**Note:** _For those who don't know, the type of argument depends on its position relative to the 3 syntax's `/`, `*`,
and `**`:_

```python
def f(po0, ___, /, pok0, ____, *args, kw0, kw1, _____, **kwargs):
#    ---------     -----------    |   ----------------     |
#    |             |              |   |                    |
#    |             Positional -   |   |                Varkeywords
#    |             or -keyword    |   Keyword - only
#    Positional - only         Varargs
    ...
```

**Note:** _The aliases `wrapper, func, default` are assured to be different from the original arguments' names._

#### Docstring formatting

By configuring `@named_default_args(format_doc=True)` (which is the default behavior), the decorator will try to bind
the default values of arguments with names defined in format keys `{[argument_name]}` in the docstring.
Any modification to the `value` property of `named_default` will update the docstring with an event.

```python
named_default('a1').value *= 2
named_default('a3').value = range(10)
named_default('a7').value = 'rust'
help(foo)
```

Output: _(even normal default arguments will be formatted)_

```
foo(a0, a1=10, a2=3, /, a3=range(0, 10), a4=-1, *a5, a6=None, a7='rust', **a8)
    A Foo function that has dynamic default arguments.
    
    Args:
        a0: Required Positional-only argument a0.
        a1: Positional-only argument a1. Dynamically defaults to a0=10.
        a2: Positional-only argument a1. Defaults to 3.
        a3: Positional-or-keyword argument a2. Dynamically defaults to a3=range(0, 10).
        a4: Positional-or-keyword argument a4. Defaults to -1
        *a5: Varargs a5.
        a6: Keyword-only argument a5. Defaults to None.
        a7: Keyword-only argument a6. Dynamically defaults to rust.
        **a8: Varkeywords a8.
```

#### Binding

The `named_default` object will emit an event to all registered listeners when its `value` property is modified. 
You can register your own handler by calling `.connect` method:

```python
from dynamic_default_args import named_default

variable = named_default('my_variable', None)


def on_variable_changed(value):
    print(f'Changed to {value}')


variable.connect(on_variable_changed)

# modifying the slot has no effect
# but accessing its value is much faster this way
variable._value = 'this doesn\'t work'

variable.value = 'this works!'
# Changed to this works!
```

### Limitations

This solution relies on function introspection provided by the `inspect` module, which does not work on built-in
functions (including C/C++ extensions).
However, you can wrap them with your own Python function.

For **Cython** users, a `def` or `cpdef` (which might be inspected incorrectly) function defined in `.pyx` files can be
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
