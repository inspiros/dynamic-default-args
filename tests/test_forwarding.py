"""Omitted static defaults must stay omitted across wrapper boundaries."""
import asyncio
from functools import partial, wraps
import inspect
import unittest

from dynamic_default_args import default, default_factory, dynamic_default_args

try:
    from pydantic import ValidationError, validate_call
except ImportError:
    validate_call = None


def recording(target):
    calls = []

    @wraps(target)
    def wrapper(*args, **kwargs):
        calls.append((args, kwargs.copy()))
        return target(*args, **kwargs)

    return wrapper, calls


class StaticDefaultForwardingTest(unittest.TestCase):
    def test_static_defaults_are_omitted_before_and_after_dynamic_defaults(self):
        sentinel = object()

        def target(before=sentinel, value=default(3), after=sentinel, *, key=sentinel):
            return before, value, after, key

        target, calls = recording(target)
        wrapped = dynamic_default_args(target)
        self.assertEqual(wrapped(), (sentinel, 3, sentinel, sentinel))
        self.assertEqual(calls, [((), {"value": 3})])
        self.assertEqual(inspect.signature(wrapped), inspect.signature(target))

    def test_explicit_static_values_including_sentinels_are_forwarded(self):
        sentinel = object()
        cell = default(3)

        def target(before=sentinel, value=cell, after=sentinel, *, key=sentinel):
            return before, value, after, key

        target, calls = recording(target)
        wrapped = dynamic_default_args(target)
        self.assertEqual(wrapped(sentinel, after=sentinel, key=sentinel),
                         (sentinel, 3, sentinel, sentinel))
        self.assertEqual(calls[-1], ((sentinel, 3, sentinel), {"key": sentinel}))
        self.assertEqual(wrapped(after=None, value=cell), (sentinel, cell, None, sentinel))
        self.assertEqual(calls[-1], ((), {"value": cell, "after": None}))

    def test_static_dependencies_are_read_without_being_forwarded(self):
        sentinel = object()
        seen = []

        def factory(value):
            seen.append(value)
            return 7

        def target(before=sentinel, value=default_factory(factory, depends_on=("before",)),
                   *, static_key=sentinel,
                   key=default_factory(factory, depends_on=("static_key",))):
            return before, value, static_key, key

        target, calls = recording(target)
        wrapped = dynamic_default_args(target)
        self.assertEqual(wrapped(), (sentinel, 7, sentinel, 7))
        self.assertEqual(seen, [sentinel, sentinel])
        self.assertEqual(calls[-1], ((), {"value": 7, "key": 7}))
        wrapped(2, static_key=4)
        self.assertEqual(seen[-2:], [2, 4])
        self.assertEqual(calls[-1], ((2, 7), {"static_key": 4, "key": 7}))

    def test_unused_static_dependency_does_not_force_forwarding(self):
        sentinel = object()

        def target(static=sentinel, value=default_factory(lambda x: x, depends_on=("static",))):
            return static, value

        target, calls = recording(target)
        wrapped = dynamic_default_args(target)
        self.assertEqual(wrapped(value=9), (sentinel, 9))
        self.assertEqual(calls[-1], ((), {"value": 9}))

    def test_positional_only_gaps_are_filled_only_when_required(self):
        sentinel = object()

        def target(first=sentinel, second=sentinel, /, value=default(3)):
            return first, second, value

        target, calls = recording(target)
        wrapped = dynamic_default_args(target)
        self.assertEqual(wrapped(), (sentinel, sentinel, 3))
        self.assertEqual(calls[-1], ((), {"value": 3}))
        self.assertEqual(wrapped(1), (1, sentinel, 3))
        self.assertEqual(calls[-1], ((1,), {"value": 3}))

        def positional(first=sentinel, value=default(3), last=sentinel, /):
            return first, value, last

        positional, calls = recording(positional)
        wrapped = dynamic_default_args(positional)
        self.assertEqual(wrapped(), (sentinel, 3, sentinel))
        self.assertEqual(calls[-1], ((sentinel, 3), {}))

    def test_positional_only_names_can_also_appear_in_extra_keywords(self):
        sentinel = object()

        def target(static=sentinel, /, value=default(3), **kwargs):
            return static, value, kwargs

        target, calls = recording(target)
        wrapped = dynamic_default_args(target)
        self.assertEqual(wrapped(static=9), (sentinel, 3, {"static": 9}))
        self.assertEqual(calls[-1], ((), {"value": 3, "static": 9}))

    def test_variadic_arguments_and_dependencies(self):
        sentinel = object()

        def target(static=sentinel, value=default(3), *args, key=sentinel,
                   derived=default_factory(tuple, depends_on=("args",)), **kwargs):
            return static, value, args, key, derived, kwargs

        target, calls = recording(target)
        wrapped = dynamic_default_args(target)
        self.assertEqual(wrapped(extra=9),
                         (sentinel, 3, (), sentinel, (), {"extra": 9}))
        self.assertEqual(calls[-1], ((), {"value": 3, "derived": (), "extra": 9}))
        self.assertEqual(wrapped(1, 2, 3, 4, extra=9),
                         (1, 2, (3, 4), sentinel, (3, 4), {"extra": 9}))
        self.assertEqual(calls[-1][0], (1, 2, 3, 4))
        self.assertNotIn("key", calls[-1][1])

    def test_partial_bound_static_default_remains_with_partial(self):
        sentinel = object()

        def target(static=sentinel, value=default_factory(lambda x: x, depends_on=("static",))):
            return static, value

        bound, calls = recording(partial(target, static=7))
        wrapped = dynamic_default_args(bound)
        self.assertEqual(wrapped(), (7, 7))
        self.assertEqual(calls[-1], ((), {"value": 7}))
        self.assertEqual(wrapped(static=9), (9, 9))
        self.assertEqual(calls[-1], ((), {"static": 9, "value": 9}))

    def test_bound_method_dependencies_keep_static_defaults_omitted(self):
        sentinel = object()

        class Client:
            value = 8

            def target(self, static=sentinel,
                       value=default_factory(lambda self, static: (self.value, static),
                                             depends_on=("self", "static"))):
                return value

            target, calls = recording(target)

        client = Client()
        wrapped = dynamic_default_args(client.target)
        self.assertEqual(wrapped(), (8, sentinel))
        self.assertEqual(Client.calls[-1], ((client,), {"value": (8, sentinel)}))

    def test_forced_and_documentation_only_wrappers_preserve_omission(self):
        sentinel = object()

        def target(static=sentinel):
            """Default {static}."""
            return static

        target, calls = recording(target)
        for options in ({}, {"force_wrap": True, "format_doc": False}):
            with self.subTest(options=options):
                self.assertIs(dynamic_default_args(**options)(target)(), sentinel)
                self.assertEqual(calls[-1], ((), {}))

    def test_keyword_only_dynamic_default_with_external_mapping(self):
        sentinel = object()

        def target(*, static=sentinel, value=0):
            return static, value

        target, calls = recording(target)
        wrapped = dynamic_default_args(defaults={"value": default(3)})(target)
        self.assertEqual(wrapped(), (sentinel, 3))
        self.assertEqual(calls[-1], ((), {"value": 3}))

    def test_async_and_generator_targets_receive_only_dynamic_defaults(self):
        sentinel = object()
        signature = inspect.signature(lambda static=sentinel, value=default(3): None)
        calls = []

        async def coroutine(*args, **kwargs):
            calls.append((args, kwargs))
            return 1

        def generator(*args, **kwargs):
            calls.append((args, kwargs))
            yield 2

        async def async_generator(*args, **kwargs):
            calls.append((args, kwargs))
            yield 3

        for target in (coroutine, generator, async_generator):
            target.__signature__ = signature

        async def run():
            self.assertEqual(await dynamic_default_args(coroutine)(), 1)
            self.assertEqual(list(dynamic_default_args(generator)()), [2])
            self.assertEqual([x async for x in dynamic_default_args(async_generator)()], [3])
            self.assertEqual(await dynamic_default_args(coroutine)(4), 1)
            self.assertEqual(list(dynamic_default_args(generator)(4)), [2])
            self.assertEqual([x async for x in dynamic_default_args(async_generator)(4)], [3])

        asyncio.run(run())
        self.assertEqual(calls, [((), {"value": 3})] * 3 + [((4, 3), {})] * 3)

    def test_explicit_signature_still_supplies_static_defaults(self):
        # The signature may describe a callable that has no defaults of its own.
        P = inspect.Parameter
        signature = inspect.Signature([
            P("x", P.POSITIONAL_OR_KEYWORD), P("y", P.POSITIONAL_OR_KEYWORD, default=7),
            P("z", P.POSITIONAL_OR_KEYWORD, default=default(0)), P("k", P.KEYWORD_ONLY, default=8)])
        wrapped = dynamic_default_args(signature=signature)(lambda *args, **kwargs: (args, kwargs))
        self.assertEqual(wrapped(20), ((20, 7, 0), {"k": 8}))
        self.assertEqual(wrapped(20, z=1, k=2), ((20, 7, 1), {"k": 2}))


@unittest.skipIf(validate_call is None, "Install pydantic>=2 for validation integration tests")
class PydanticForwardingTest(unittest.TestCase):
    def test_static_sentinel_is_omitted_but_dynamic_values_are_validated(self):
        sentinel = object()
        cell = default(3)

        @dynamic_default_args(defaults={"value": cell})
        @validate_call
        def target(static: int = sentinel, value: int = 0, *, static_key: int = sentinel):
            return static, value, static_key

        self.assertEqual(target(), (sentinel, 3, sentinel))
        cell.value = "4"
        self.assertEqual(target(), (sentinel, 4, sentinel))
        cell.value = "invalid"
        with self.assertRaises(ValidationError):
            target()
        self.assertEqual(target(value=5), (sentinel, 5, sentinel))
        for kwargs in ({"static": sentinel}, {"static_key": sentinel}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                target(value=5, **kwargs)
        with self.assertRaises(ValidationError):
            target(sentinel, value=5)

    def test_markers_in_signature_compose_with_pydantic(self):
        sentinel = object()
        cell = default(3)

        @dynamic_default_args
        @validate_call
        def target(static: int = sentinel, value: int = cell):
            return static, value

        self.assertEqual(target(), (sentinel, 3))
        cell.value = "4"
        self.assertEqual(target(), (sentinel, 4))
        cell.value = "invalid"
        with self.assertRaises(ValidationError):
            target()

    def test_factory_can_depend_on_unvalidated_static_sentinel(self):
        sentinel = object()
        marker = default_factory(lambda x: "7" if x is sentinel else x + 1,
                                 depends_on=("static",))

        @dynamic_default_args(defaults={"value": marker})
        @validate_call
        def target(static: int = sentinel, value: int = 0):
            return static, value

        self.assertEqual(target(), (sentinel, 7))
        self.assertEqual(target(2), (2, 3))
