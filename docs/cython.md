# Cython compatibility

Cython is an optional integration target, not a runtime dependency. Cython 3 enables
Python-style binding/introspection by default. Keep `binding=True`; an explicit
signature can describe other callables, but cannot change their native behavior.

## Typed def functions

Cython needs valid default values during module initialization. A marker cannot
be used as a numeric C default. Annotations such as `x: float` may also infer a C
type. Put markers in the decorator instead:

```cython
from dynamic_default_args import default, dynamic_default_args

timeout = default(1.0)

@dynamic_default_args(defaults={"x": timeout})
def compute(double x=0.0):
    return x * 2
```

`compute()` resolves `timeout.value`, then passes it through Cython's normal
conversion. `compute(2.0)` uses the explicit value. Values incompatible with the
C type still raise a conversion error. The original native default remains 0.0.
For untyped object parameters, defaults in the signature also work.

## cpdef functions

Cython rejects arbitrary Python decorators directly on `cpdef` functions. Export
a separate Python wrapper instead:

```cython
from dynamic_default_args import default, dynamic_default_args

rate = default(2.0)

cpdef double native_compute(double x=0.0):
    return x * 2

compute = dynamic_default_args(defaults={"x": rate})(native_compute)
```

Python callers use `compute`. Cython callers of `native_compute()` retain native
C defaults. A decorator does not intercept C-level calls. Changing a module's
Python attribute does not rewrite compiled call sites.

`cdef` functions are not Python callables and cannot be decorated. To apply the
same policy to C-level callers, write an explicit Cython entry point that reads
configuration and calls the native function, paying any required Python/GIL cost.

## Methods and extension types

Methods on ordinary Python classes compiled by Cython work with the decorator.
For a method on a `cdef class`, an external wrapper around a bound method can use
`defaults=`. This avoids trying to replace descriptors on an immutable extension
type. C-level dispatch remains outside the Python wrapper.

The compiled test fixture covers untyped `def`, C-typed and annotation-inferred
`def`, Python-callable `cpdef`, compiled native calls, compiled Python classes,
and bound extension methods. It does not claim to cover every Cython directive,
C-level dispatch mode, extension inheritance pattern, or third-party extension.

Run the integration tests with:

```bash
python -m pip install -e '.[cython]'
DDA_TEST_CYTHON=1 python -m unittest discover -s tests -v
```

The environment variable makes compilation mandatory. Missing compiler tools
cause a failure rather than a misleading skip. Generated files go under `develop/`.
