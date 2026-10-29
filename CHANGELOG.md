# Changelog

## 0.1.0

- Add per-call factories with dependencies on earlier parameters.
- Support decorator-supplied defaults, including for C-typed Cython arguments.
- Preserve native positional-only, keyword-only, and variadic argument binding.
- Support methods, both descriptor decorator orders, bound methods, partials,
  callable instances, and inspectable built-ins; accept explicit signatures.
- Preserve coroutine, generator, and async generator behavior and protocols.
- Prevent helper-name collisions and avoid embedding user object representations
  in executable source.
- Use weak internal documentation subscriptions and snapshot event dispatch.
- Preserve literal docstring braces and unknown placeholders.
- Add named-default registry removal.
- Preserve factory dependencies through callable-instance and partial binding,
  including partial-bound variadic arguments.
- Correct async-generator forwarding of explicit `GeneratorExit` and ignore
  instance attributes shadowing the type's `__call__` implementation.
- Consolidate packaging in pyproject.toml. Publish manually from a version tag
  after its tests pass, with a pure-Python wheel alongside the source archive.
- Require Python 3.8+. Explicit arguments, including marker instances, now pass
  through unchanged.
