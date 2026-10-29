"""Behavioral regressions found by the independent review."""
import asyncio
from functools import partial, update_wrapper
import inspect
import sys
import unittest

from dynamic_default_args import default, default_factory, dynamic_default_args, named_default


class CallableBindingTest(unittest.TestCase):
    def test_callable_factory_can_depend_on_self(self):
        class C:
            value = 7

            def __call__(self, x=default_factory(lambda self: self.value, depends_on=("self",))):
                return x

        instance = C()
        wrapped = dynamic_default_args()(instance)
        self.assertEqual(wrapped(), 7)
        instance.value = 9
        self.assertEqual(wrapped(), 9)
        self.assertIsNone(wrapped(None))
        self.assertEqual(list(inspect.signature(wrapped).parameters), ["x"])

    def test_partial_factory_can_depend_on_bound_parameter(self):
        def f(a, x=default_factory(lambda a: a + 1, depends_on=("a",))):
            return a, x

        wrapped = dynamic_default_args()(partial(f, 2))
        self.assertEqual(wrapped(), (2, 3))
        self.assertEqual(wrapped(10), (2, 10))
        self.assertEqual(list(inspect.signature(wrapped).parameters), ["x"])
        with self.assertRaises(TypeError):
            wrapped(a=3)

    def test_keyword_partial_dependency_and_override(self):
        def f(a, x=default_factory(lambda a: a + 1, depends_on=("a",))):
            return a, x

        wrapped = dynamic_default_args()(partial(f, a=2))
        self.assertEqual(wrapped(), (2, 3))
        self.assertEqual(wrapped(a=4), (4, 5))
        with self.assertRaises(TypeError):
            wrapped(3)

    def test_partial_factory_receives_all_varargs(self):
        def f(*args, x=default_factory(len, depends_on=("args",))):
            return args, x

        wrapped = dynamic_default_args()(partial(f, 1, 2))
        self.assertEqual(wrapped(), ((1, 2), 2))
        self.assertEqual(wrapped(3, 4), ((1, 2, 3, 4), 4))
        self.assertEqual(wrapped(3, x=None), ((1, 2, 3), None))

    def test_partial_bound_marker_is_an_explicit_value(self):
        def f(a=default(1), x=default_factory(lambda a: a, depends_on=("a",))):
            return a, x

        cell = default(7)
        for target in (partial(f, cell), partial(f, a=cell)):
            with self.subTest(target=target):
                result = dynamic_default_args()(target)()
                self.assertIs(result[0], cell)
                self.assertIs(result[1], cell)

    def test_partial_defaults_mapping_and_formatted_doc(self):
        def f(a, x=0):
            return a, x

        target = partial(f, 2)
        target.__doc__ = "Value {x}."
        cell = default(3)
        wrapped = dynamic_default_args(defaults={"x": cell})(target)
        self.assertEqual(wrapped(), (2, 3))
        self.assertEqual(wrapped.__doc__, "Value 3.")
        cell.value = 5
        self.assertEqual(wrapped(), (2, 5))
        self.assertEqual(wrapped.__doc__, "Value 5.")
        self.assertIs(inspect.signature(wrapped).parameters["x"].default, cell)
        with self.assertRaises(ValueError):
            dynamic_default_args(defaults={"a": default(4)})(target)

    def test_nested_partial_of_callable_instance(self):
        class C:
            value = 3

            def __call__(self, a, x=default_factory(lambda self, a: self.value + a,
                                                   depends_on=("self", "a"))):
                return x

        wrapped = dynamic_default_args()(partial(partial(C(), 2)))
        self.assertEqual(wrapped(), 5)

    def test_partial_override_can_make_a_required_parameter_optional(self):
        def f(a, b, c):
            return a, b, c

        target = partial(f, b=2)
        wrapped = dynamic_default_args(defaults={"a": default(1)})(target)
        self.assertEqual(wrapped(c=3), (1, 2, 3))
        self.assertEqual(wrapped(4, b=5, c=6), (4, 5, 6))
        with self.assertRaises(TypeError):
            wrapped()

    def test_partial_subclass_call_behavior_is_preserved(self):
        class P(partial):
            def __call__(self, *args, **kwargs):
                return "custom"

        target = P(lambda x=default(1): x)
        self.assertEqual(dynamic_default_args()(target)(), "custom")

    def test_callable_wrapper_signature_is_honored(self):
        def f(x=default(1)):
            return x

        class Wrapper:
            def __init__(self, function):
                update_wrapper(self, function)

            def __call__(self, *args, **kwargs):
                return self.__wrapped__(*args, **kwargs)

        wrapped = dynamic_default_args()(Wrapper(f))
        self.assertEqual(wrapped(), 1)
        self.assertIsNone(wrapped(None))

    def test_partial_noop_with_documentation_disabled(self):
        target = partial(lambda x=1: x)
        target.__doc__ = "Default {x}."
        self.assertIs(dynamic_default_args(format_doc=False)(target), target)

    def test_call_kind_ignores_instance_shadowing(self):
        class C:
            def __call__(self, x=default(2)):
                return x

        async def shadow():
            return 100

        instance = C()
        instance.__call__ = shadow
        wrapped = dynamic_default_args()(instance)
        self.assertFalse(inspect.iscoroutinefunction(wrapped))
        self.assertEqual(wrapped(), 2)

    def test_noop_descriptors_and_methods_keep_identity(self):
        class C:
            def f(self):
                return 1

        method = C().f
        self.assertIs(dynamic_default_args()(method), method)
        for descriptor in (staticmethod(C.f), classmethod(C.f)):
            self.assertIs(dynamic_default_args()(descriptor), descriptor)
        target = partial(lambda a: a, 1)
        self.assertIs(dynamic_default_args()(target), target)

    def test_listener_identity_does_not_invoke_custom_equality(self):
        calls = []

        class Listener:
            def __call__(self, value):
                calls.append(value)

            def __eq__(self, other):
                raise AssertionError("Listener identity must not depend on value equality")

        first, second = Listener(), Listener()
        cell = default(0)
        cell.connect(first)
        cell.connect(first)
        cell.connect(second)
        cell.value = 1
        self.assertEqual(calls, [1, 1])
        cell.disconnect(first)
        cell.value = 2
        self.assertEqual(calls, [1, 1, 2])

    def test_bound_listener_identity(self):
        calls = []

        class Listener:
            def callback(self, value):
                calls.append(value)

        instance = Listener()
        cell = default(0)
        cell.connect(instance.callback)
        cell.connect(instance.callback)
        cell.value = 1
        cell.disconnect(instance.callback)
        cell.value = 2
        self.assertEqual(calls, [1])

    def test_builtin_bound_listener_identity(self):
        calls = []
        cell = default(0)
        cell.connect(calls.append)
        cell.connect(calls.append)
        cell.value = 1
        cell.disconnect(calls.append)
        cell.value = 2
        self.assertEqual(calls, [1])

    def test_weak_builtin_bound_listener_is_rejected(self):
        cell = default(0)
        with self.assertRaisesRegex(TypeError, "built-in bound methods"):
            cell.connect([].append, weak=True)
        cell.connect(len, weak=True)  # A module-level built-in outlives the call.
        self.assertEqual(len(cell._listeners), 1)

    def test_unformattable_doc_field_does_not_break_assignment(self):
        n = default(3)
        seen = []

        @dynamic_default_args
        def f(n=n):
            """n is {n:d}."""
            return n

        n.connect(seen.append)
        n.value = 2.5
        self.assertEqual((f(), seen, f.__doc__), (2.5, [2.5], "n is {n:d}."))
        n.value = 4
        self.assertEqual(f.__doc__, "n is 4.")

    def test_concurrent_named_registration_returns_one_cell(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        name = "test_review_concurrent_registration"
        named_default.unregister(name)
        self.addCleanup(named_default.unregister, name)
        barrier = Barrier(8)

        def register(value):
            barrier.wait(timeout=10)
            return named_default(name, value)

        with ThreadPoolExecutor(max_workers=8) as pool:
            cells = list(pool.map(register, range(8)))
        self.assertTrue(all(cell is cells[0] for cell in cells))

    @unittest.skipUnless(sys.version_info >= (3, 14), "PEP 649 lazy annotations")
    def test_lazy_annotations_on_partials_and_callable_instances(self):
        namespace = {"default": default, "calls": []}
        exec(compile("def f(a, x: calls.append(1) or Later = default(1)): return a, x\n"
                     "class C:\n    def __call__(self, x: calls.append(2) or Later = default(2)): return x\n"
                     "class Later: pass", "<callable lazy annotations>", "exec", dont_inherit=True),
             namespace)
        wrapped_partial = dynamic_default_args()(partial(namespace["f"], 3))
        wrapped_instance = dynamic_default_args()(namespace["C"]())
        self.assertEqual(namespace["calls"], [])
        self.assertEqual(wrapped_partial(), (3, 1))
        self.assertEqual(wrapped_instance(), 2)


class AsyncGeneratorReviewTest(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_generator_exit_can_be_caught_and_yield(self):
        closed = []

        @dynamic_default_args
        async def f(x=default(1)):
            try:
                try:
                    yield x
                except GeneratorExit:
                    yield "caught"
            finally:
                closed.append(True)

        iterator = f()
        self.assertEqual(await iterator.__anext__(), 1)
        self.assertEqual(await iterator.athrow(GeneratorExit()), "caught")
        await iterator.aclose()
        self.assertEqual(closed, [True])

    async def test_aclose_rejects_yielding_after_generator_exit(self):
        async def f(x=default(1)):
            try:
                yield x
            except GeneratorExit:
                yield "invalid during close"

        for target in (f, dynamic_default_args(f)):
            with self.subTest(target=target):
                iterator = target()
                await iterator.__anext__()
                with self.assertRaisesRegex(RuntimeError, "ignored GeneratorExit"):
                    await iterator.aclose()
                # Drain the invalid generator. Some Python versions also raise
                # StopAsyncIteration from a second native aclose() in this case.
                with self.assertRaises(StopAsyncIteration):
                    await iterator.__anext__()

    async def test_partial_async_callable_keeps_kind_and_dependencies(self):
        class C:
            value = 5

            async def __call__(self, a, x=default_factory(lambda self, a: self.value + a,
                                                         depends_on=("self", "a"))):
                return x

        wrapped = dynamic_default_args()(partial(C(), 2))
        self.assertTrue(inspect.iscoroutinefunction(wrapped))
        self.assertEqual(await wrapped(), 7)
        with self.assertRaises(TypeError):
            default_factory(C())
        with self.assertRaises(TypeError):
            default_factory(partial(C(), 2))
        signature = inspect.Signature([
            inspect.Parameter("x", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default(3))])
        explicit = dynamic_default_args(signature=signature)(partial(C(), 2))
        self.assertTrue(inspect.iscoroutinefunction(explicit))
        self.assertEqual(await explicit(), 3)

    async def test_cancellation_closes_underlying_generator(self):
        closed = []
        ready = asyncio.Event()

        @dynamic_default_args
        async def f(x=default(1)):
            try:
                ready.set()
                await asyncio.Event().wait()
                yield x
            finally:
                closed.append(True)

        iterator = f()
        task = asyncio.create_task(iterator.__anext__())
        await ready.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(closed, [True])
