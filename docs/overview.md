# Project assessment

Assessment date: 2026-10-29. Original version: 0.0.6. Overhaul: 0.1.0.

## Is the gap still real?

Yes. The [Python language reference](https://docs.python.org/3/reference/compound_stmts.html#function-definitions)
still specifies that default expressions run when a function is defined.
[PEP 671](https://peps.python.org/pep-0671/) remains Draft; its proposed `=>` syntax
is not available in ordinary Python. Its historical Python-Version field is a
proposal target, not evidence that the feature shipped.

Sentinel checks in a function body remain a good standard solution. Dataclasses
have [field factories](https://docs.python.org/3/library/dataclasses.html#default-factory-functions),
but that facility does not extend to arbitrary function parameters.

There are three distinct needs:

| Need | Example | Original package | Version 0.1.0 |
| --- | --- | --- | --- |
| Shared configurable value | Update the timeout of multiple functions | Yes | `default`, `named_default` |
| Compute a new value on each omission | Fresh list, current time, current configuration | No | `default_factory` |
| Depend on arguments to this call | Limit based on `len(items)`, instance configuration | No | Factory with explicit `depends_on` |

This package remains useful even if Python gains late-bound syntax: shared named
configuration is a separate facility. It should not promise a transparent PEP 671
implementation. Factories are callables with their own lexical scope, rather than
expressions evaluated inside the decorated function's local scope.

## Original structure and behavior

The original project had approximately 300 lines of runtime code:

- `dynamic_default_args.py`: shared default objects, the global name registry,
  and a decorator generating Python source for a forwarding function.
- `event.py`: change notifications stored in a set.
- `format_dict.py`: missing docstring format fields became `...`.
- One example and 12 tests, all covering the named-default constructor and updates.
- Split setuptools configuration, plus a tag-triggered wheel/publishing workflow.

The central trick is ordinary Python code generation, not interpreter patching.
A wrapper uses the function's default objects and reads their current values on
each call. `functools.wraps` exposes the original signature to inspection.

## Was the trick a good approach?

The idea is defensible. A generated function can let Python do argument binding,
then resolve defaults with a few checks. It avoids a full `Signature.bind()` and
argument dictionary reconstruction on every call. It needs neither bytecode
rewriting nor writable `__defaults__`, and can therefore adapt Cython's Python
interfaces as well as ordinary functions.

The original implementation's main weakness was incomplete generation of the
signature, rather than generation itself. The new implementation uses
`inspect.Signature` to render `/`, `*`, and variadic boundaries, with safe global
references for default objects. It never interpolates a user's value or annotation
representation into executable source. Private helper names avoid parameter-name
collisions. The wrapper calls the original function and leaves its defaults alone.

Runtime source generation has costs: an extra frame, an extra call, harder source
stepping, and deployment environments that may prohibit `exec`. It should stay
small and receive semantic tests. An ordinary in-body sentinel check is still
simpler and faster for a single function.

Mutating `__defaults__` is not the general solution: it mutates the original
function, cannot compute factories per omission, does not universally work for
extension callables, and can lead to cross-call interference if used to emulate
per-call values. Rewriting bytecode would make version compatibility much harder.
A generic bind-on-every-call wrapper is simpler, but measurably slower for tiny
functions; `develop/benchmark.py` allows that comparison on the local machine.

## Confirmed baseline problems

The 12 original tests passed on CPython 3.10, 3.12, and 3.13. Disposable probes in
`develop/audit.py` exposed these failures in 0.0.6:

| Case | Original result | Overhaul |
| --- | --- | --- |
| Positional-only name also supplied through `**kwargs` | Incorrect multiple-values error | Preserves `/` |
| Keyword-only parameter without `*args` | Accepted forbidden positional arguments | Preserves bare `*` |
| Required keyword-only parameter after an optional positional parameter | Decoration raised `SyntaxError` | Valid wrapper |
| Parameter named `isinstance` | Shadowed helper and caused `TypeError` | Collision-free aliases |
| Coroutine/generator function inspection | False even though returned objects worked | Correct wrapper kind |
| `classmethod` applied before the decorator | `TypeError` | Both orders supported |
| Callable instance | Missing `__name__` caused `AttributeError` | Supported |
| Literal JSON braces alongside doc placeholders | Formatting could fail | Only known simple fields substituted |
| Functions using a registered named value and formatted docs | Retained indefinitely through listeners | Weak internal subscriptions |
| Listener disconnecting itself | Set mutation error | Snapshot dispatch |
| Explicit marker argument | Silently unwrapped | Preserved as an explicit value |

The README's blanket claim that built-ins cannot be inspected was too broad:
`inspect.signature(len)` works. Some built-ins lack usable metadata; explicit
`signature=` is now the escape hatch. A signature only describes how to call a
function; it cannot make an incompatible native API accept those arguments.

The original release workflow also had an empty step, a reference to nonexistent
`build_wheels` instead of `build_wheel`, no test matrix, and old artifact actions.
The package advertised every Python 3 version despite requiring newer syntax.

## Cython findings

Cython 3.3.0 experiments confirmed that basic compiled `def` functions still work.
The [binding directive has defaulted to True since Cython 3](https://cython.readthedocs.io/en/latest/src/userguide/migrating_to_cy30.html#binding-functions).
However, typed defaults must be convertible when the extension initializes.
`def f(double x=default(1.0))` fails because the marker is not a real number.
Cython may also infer C types from Python annotations.

Decorator-supplied defaults avoid that problem: compile a valid native default,
then resolve the dynamic value in a Python wrapper before native conversion.
Direct arbitrary decorators on `cpdef` are rejected by Cython. Wrapping an already
compiled `cpdef` provides a Python entry point; C-level calls keep native behavior.
See [the compatibility guide](cython.md) for the exact supported boundary.

## Recommendation

Pursue a small dependency-free library with an explicit contract. Keep shared
values, add synchronous factories and explicit dependencies, and maintain generated
wrappers only while they remain easy to test and worthwhile for call overhead.
Prioritize native binding behavior, methods, coroutine/generator protocols, and
compiled integration tests over pretending every C or Python callable is identical.

The release should describe intentional changes, especially omission-only marker
resolution and the Python 3.10 minimum. CI should test supported Python versions
and compiled Cython fixtures on Linux, Windows, and macOS before publication.
