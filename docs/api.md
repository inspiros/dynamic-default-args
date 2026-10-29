# API and semantics

## Shared defaults

```python
from dynamic_default_args import default, named_default, dynamic_default_args

shared = default(5)

@dynamic_default_args()
def connect(timeout=shared):
    return timeout

shared.value = 10
assert connect() == 10
assert connect(None) is None
```

`default(value)` holds an object; it does not copy it or invoke callable values.
Mutable values are therefore shared. Use a factory for fresh mutable objects.

`named_default("timeout", 5)`, `named_default(name="timeout", value=5)`, and
`named_default(timeout=5)` register or retrieve a process-wide named cell. First
registration wins; subsequent initialization values are ignored. Retrieve it with
`named_default("timeout")`. Use namespaced names to avoid unrelated modules
colliding. `named_default.unregister("timeout")` removes the registry entry;
existing functions keep their original cell. Registration is protected by a lock.

## Per-call factories

```python
from dynamic_default_args import default_factory, dynamic_default_args

@dynamic_default_args
def take(items, limit=default_factory(len, depends_on=("items",)), *,
         output=default_factory(list)):
    output.extend(items[:limit])
    return output

assert take([1, 2, 3]) == [1, 2, 3]
assert take([1, 2, 3], 1) == [1]
```

`default_factory(callable, *, depends_on=())` runs once for each omitted argument.
Dependencies name earlier parameters, in the order passed to the factory as
positional arguments. Resolution proceeds left to right. Dependencies see explicit
values or already resolved defaults. A later parameter, self-reference, or unknown
name is an error at decoration time. Factories may depend on `self`, `cls`, or
an earlier `*args` tuple. They cannot depend on a later `**kwargs` parameter.

Factories are synchronous. Async functions are rejected as factories; factories
are not automatically awaited. Exceptions propagate to the caller. A callable
object that returns an awaitable will pass that object as a value; avoid doing so
unless that is intentional.

An explicit argument always wins, including `None`, false values, and marker
objects. Factories are not run for calls rejected by native argument binding.

## Decorator options

`@dynamic_default_args` and `@dynamic_default_args(...)` both work.

- `format_doc=True`: substitute known simple fields such as `{timeout}`, `{timeout!r}`,
  and `{timeout:.2f}`. Shared-value assignments update those fields through weak
  internal subscriptions. Unknown fields, literal braces, escaped braces, and
  factory fields remain unchanged. Factories never run for documentation.
  Formatting errors for a known field propagate.
- `force_wrap=False`: produce a wrapper even without dynamic defaults when True.
- `defaults={"parameter": marker}`: supply shared defaults or factories outside the
  function definition. Useful for typed Python and Cython functions. All keys
  must name non-variadic parameters. The resulting parameter order must remain a
  valid Python signature. Required parameters can become optional when valid.
- `signature=inspect.Signature(...)`: explicitly describe a callable that lacks
  introspection metadata. This is a caller-supplied adapter contract.

Type annotations do not run through generated source. `__wrapped__`, annotations,
type parameters where supported, and the public signature are preserved by
`functools.update_wrapper`. `inspect.signature()` shows shared cells through their
current representation and factories through descriptive markers. Internal wrapper
`__defaults__` contain omission sentinels; inspect the public signature instead.
The original function's defaults are unchanged.
On Python 3.14+, ordinary function wrappers leave lazy annotations unevaluated
during decoration. Explicit signature overrides may evaluate annotations to build
their public signature; unresolved forward references are retained as strings.

Instance methods, inheritance, and class/static methods work. Both decorator
orders with `classmethod` and `staticmethod` are supported. Bound methods,
partials, callable instances, and inspectable built-ins can also be adapted.
For callable classes with unusual custom signatures, supply a matching signature.

Coroutines remain coroutine functions. Generators preserve `send`, `throw`,
`close`, and return values. Async generators forward `asend`, `athrow`, and
`aclose`. For coroutines, resolution occurs when execution starts; for generators,
on first iteration. It does not happen merely when the suspended object is created.

## Events and concurrency

`cell.connect(callback)` and `@cell.on` register synchronous listeners.
`connect(callback, weak=True)` weakly subscribes a weak-referenceable callable.
`disconnect(callback)` and `disconnect_all()` remove subscriptions.
Dispatch uses a snapshot in registration order, so listeners can change subscriptions;
changes affect later notifications. An exception stops that dispatch and propagates,
after the cell's value has already changed. In-place mutation does not emit events.

Internal docstring listeners do not keep discarded functions alive. User listeners
are strong by default. Registry entries remain until unregistered. Registry and
subscription changes are locked, but an entire call does not take an atomic snapshot
of multiple defaults. Factories and user callbacks must handle their own concurrency.
No free-threaded runtime compatibility claim is made without a dedicated test matrix.

## Migrating from 0.0.6

- Python 3.10 is now the minimum supported version.
- Explicit marker arguments are passed through; only omitted arguments resolve.
  Previously any `default` instance supplied to a dynamic parameter was unwrapped.
  To pass the contained value explicitly, use `cell.value`.
- Factory support is new. Existing `default(callable)` still passes that callable.
- Doc formatting preserves unknown fields rather than replacing them with `...`.
  Compound fields such as `{x.attribute}` are not substituted.
- Coroutines and generators resolve when their body begins, preserving function kind.
- Supply typed Cython defaults in the decorator, not as C parameter marker values.
- Prefer keyword options. The legacy `dynamic_default_args(False)` spelling for
  `format_doc=False` is also accepted.
