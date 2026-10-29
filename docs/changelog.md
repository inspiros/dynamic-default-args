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
- Consolidate packaging in pyproject.toml and replace the release workflow with
  test/build jobs and PyPI trusted publishing.
- Require Python 3.10+. Explicit arguments, including marker instances, now pass
  through unchanged. See [migration notes](api.md#migrating-from-006).
