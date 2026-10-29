import asyncio
import functools
import gc
import inspect
import sys
import unittest
import weakref

from dynamic_default_args import default, default_factory, dynamic_default_args, named_default


class DynamicDefaultsTest(unittest.TestCase):
    def test_shared_value_and_explicit_values(self):
        cell = default(1)

        @dynamic_default_args
        def f(x=cell):
            return x

        self.assertEqual(f(), 1)
        cell.value = 2
        self.assertEqual(f(), 2)
        self.assertIsNone(f(None))
        self.assertEqual(f(0), 0)
        self.assertIs(f(cell), cell)  # Explicit marker objects remain explicit.
        other = default(9)
        self.assertIs(f(other), other)

    def test_all_parameter_kinds(self):
        @dynamic_default_args()
        def f(a, b=default(2), /, c=default(3), *args, d, e=default(5), **kwargs):
            return a, b, c, args, d, e, kwargs

        self.assertEqual(f(1, d=4, b=99), (1, 2, 3, (), 4, 5, {"b": 99}))
        self.assertEqual(f(1, 6, 7, 8, d=9, e=10, z=11),
                         (1, 6, 7, (8,), 9, 10, {"z": 11}))
        with self.assertRaises(TypeError):
            f(a=1, d=4)
        with self.assertRaises(TypeError):
            f(1)
        with self.assertRaises(TypeError):
            f(1, 2, 3, c=4, d=5)

    def test_keyword_only_boundary(self):
        @dynamic_default_args()
        def f(x=default(1), *, required, y=default(2)):
            return x, required, y

        self.assertEqual(f(required=3), (1, 3, 2))
        with self.assertRaises(TypeError):
            f(1, 3)

    def test_helper_name_collisions(self):
        @dynamic_default_args()
        def f(isinstance=0, _dda_target=1, __dda_missing=2,
              func=3, wrapper=4, default=5, x=default(6)):
            return x

        self.assertEqual(f(), 6)

    def test_no_user_repr_in_generated_source(self):
        class BadRepr:
            def __repr__(self):
                raise RuntimeError("Must not render default objects during decoration")

        value = BadRepr()

        @dynamic_default_args(format_doc=False)
        def f(x=default(value), y=value):
            return x, y

        self.assertIs(f()[0], value)
        self.assertIs(f()[1], value)

    def test_factory_only_for_omission_and_fresh_objects(self):
        calls = []

        @dynamic_default_args
        def f(x=default_factory(lambda: calls.append(1) or [])):
            return x

        self.assertIsNot(f(), f())
        explicit = []
        self.assertIs(f(explicit), explicit)
        self.assertIsNone(f(None))
        self.assertEqual(len(calls), 2)
        with self.assertRaises(TypeError):
            f(1, 2)
        self.assertEqual(len(calls), 2)

    def test_factory_dependencies_and_order(self):
        @dynamic_default_args
        def f(a=default(2), b=default_factory(lambda a: a + 1, depends_on=("a",)), *,
              c=default_factory(lambda a, b: a * b, depends_on=("a", "b"))):
            return a, b, c

        self.assertEqual(f(), (2, 3, 6))
        self.assertEqual(f(4), (4, 5, 20))
        self.assertEqual(f(b=10), (2, 10, 20))
        self.assertEqual(f(c=None), (2, 3, None))

    def test_factory_exception_and_callable_value(self):
        def fail():
            raise LookupError("factory failed")

        @dynamic_default_args
        def f(x=default_factory(fail)):
            return x

        with self.assertRaisesRegex(LookupError, "factory failed"):
            f()
        self.assertEqual(f(1), 1)

        @dynamic_default_args
        def g(x=default(list)):
            return x

        self.assertIs(g(), list)

    def test_dependency_validation(self):
        for dependencies in [("missing",), ("y",), ("x",)]:
            with self.subTest(dependencies=dependencies), self.assertRaises(ValueError):
                dynamic_default_args()(lambda x=default_factory(list, depends_on=dependencies), y=1: x)
        for invalid in ["x", (1,)]:
            with self.assertRaises(TypeError):
                default_factory(list, depends_on=invalid)
        with self.assertRaises(TypeError):
            default_factory(3)

    def test_external_mapping(self):
        @dynamic_default_args(defaults={"x": default_factory(list)})
        def f(x=None):
            return x

        self.assertEqual(f(), [])
        self.assertIsNone(f(None))
        self.assertIsNot(f(), f())

    def test_external_mapping_validation(self):
        for mapping in [{"absent": default(1)}, {"args": default(1)}, {"kw": default(1)}]:
            with self.assertRaises(ValueError):
                dynamic_default_args(defaults=mapping)(lambda x=0, *args, **kw: x)
        with self.assertRaises(TypeError):
            dynamic_default_args(defaults={"x": 1})(lambda x=0: x)
        with self.assertRaises(ValueError):
            dynamic_default_args(defaults={"x": default(1)})(lambda x, y: x)

    def test_signatures_and_metadata(self):
        cell = default(1)

        def f(x: int = cell, /, *, y: str = "a") -> tuple:
            """Unchanged documentation."""
            return x, y

        wrapped = dynamic_default_args()(f)
        self.assertEqual(inspect.signature(wrapped), inspect.signature(f))
        self.assertIs(wrapped.__wrapped__, f)
        self.assertEqual(wrapped.__annotations__, f.__annotations__)
        self.assertEqual(wrapped.__name__, f.__name__)
        self.assertEqual(wrapped.__doc__, f.__doc__)
        cell.value = 4
        self.assertIn("x: int = 4", str(inspect.signature(wrapped)))
        self.assertEqual(wrapped(), (4, "a"))

    def test_plain_functions(self):
        def f():
            return 1

        self.assertIs(dynamic_default_args()(f), f)
        self.assertIs(dynamic_default_args(format_doc=False)(f), f)
        self.assertIsNot(dynamic_default_args(force_wrap=True)(f), f)
        self.assertEqual(dynamic_default_args(False)(f)(), 1)

        def ordinary(x=1):
            return x

        self.assertIs(dynamic_default_args()(ordinary), ordinary)

        def documented(x=1):
            """Default: {x}."""
            return x

        wrapped = dynamic_default_args()(documented)
        self.assertEqual(wrapped.__doc__, "Default: 1.")
        self.assertEqual(documented.__doc__, "Default: {x}.")

    def test_callable_instances_partials_and_builtins(self):
        class C:
            def __call__(self, x=default(1)):
                return x

        self.assertEqual(dynamic_default_args()(C())(), 1)
        f = functools.partial(lambda a, x=default(2): (a, x), 1)
        self.assertEqual(dynamic_default_args()(f)(), (1, 2))
        wrapped_len = dynamic_default_args(defaults={"obj": default_factory(list)})(len)
        self.assertEqual(wrapped_len(), 0)
        with self.assertRaises(TypeError):
            wrapped_len(obj=[])

    def test_explicit_signature(self):
        signature = inspect.Signature([
            inspect.Parameter("x", inspect.Parameter.POSITIONAL_ONLY, default=default(3))])
        wrapped = dynamic_default_args(signature=signature)(lambda *args: args)
        self.assertEqual(wrapped(), (3,))
        with self.assertRaises(TypeError):
            wrapped(x=3)
        with self.assertRaises(TypeError):
            dynamic_default_args(signature="bad")(len)
        with self.assertRaisesRegex(TypeError, "supply signature"):
            dynamic_default_args()(dict)

    def test_methods_both_decorator_orders_and_self_dependency(self):
        class C:
            value = 7

            @dynamic_default_args
            def method(self, x=default_factory(lambda self: self.value, depends_on=("self",))):
                return x

            @classmethod
            @dynamic_default_args()
            def class_outer(cls, x=default(2)):
                return cls, x

            @dynamic_default_args()
            @classmethod
            def class_inner(cls, x=default(3)):
                return cls, x

            @staticmethod
            @dynamic_default_args()
            def static_outer(x=default(4)):
                return x

            @dynamic_default_args()
            @staticmethod
            def static_inner(x=default(5)):
                return x

        class Child(C):
            value = 8

        self.assertEqual(C().method(), 7)
        self.assertEqual(Child().method(), 8)
        self.assertEqual(C.class_outer(), (C, 2))
        self.assertEqual(Child.class_inner(), (Child, 3))
        self.assertEqual(C.static_outer(), 4)
        self.assertEqual(C().static_inner(), 5)
        self.assertEqual(dynamic_default_args()(C().method)(), 7)

    def test_documentation_updates_without_retaining_functions(self):
        cell = named_default("test_doc_lifetime", 1)
        self.addCleanup(named_default.unregister, cell.name)

        @dynamic_default_args()
        def f(x=cell, y=2):
            """Value {x:02d}, static {y}, JSON {"key": 1}, unknown {z}, escaped {{x}}."""
            return x

        self.assertEqual(f.__doc__, 'Value 01, static 2, JSON {"key": 1}, unknown {z}, escaped {{x}}.')
        cell.value = 3
        self.assertIn("Value 03", f.__doc__)
        ref = weakref.ref(f)
        del f
        gc.collect()
        self.assertIsNone(ref())
        cell.value = 4
        self.assertEqual(len(cell._listeners), 0)

    def test_factory_not_evaluated_for_docs_or_signature(self):
        calls = []

        @dynamic_default_args
        def f(x=default_factory(lambda: calls.append(1))):
            """Factory: {x}."""
            return x

        str(inspect.signature(f))
        self.assertEqual(f.__doc__, "Factory: {x}.")
        self.assertEqual(calls, [])

    def test_events_snapshot_and_weak_bound_methods(self):
        cell = default(1)
        calls = []

        def first(value):
            calls.append(value)
            cell.disconnect(first)
            cell.connect(second)

        def second(value):
            calls.append(value * 10)

        cell.connect(first)
        cell.connect(first)
        cell.value = 2
        self.assertEqual(calls, [2])
        cell.value = 3
        self.assertEqual(calls, [2, 30])
        cell.disconnect_all()

        class Listener:
            def callback(self, value):
                calls.append(value)

        listener = Listener()
        ref = weakref.ref(listener)
        cell.connect(listener.callback, weak=True)
        del listener
        gc.collect()
        cell.value = 4
        self.assertIsNone(ref())
        self.assertEqual(calls, [2, 30])

    def test_unregister(self):
        old = named_default("test_unregister", 1)
        named_default.unregister("test_unregister")
        new = named_default("test_unregister", 2)
        self.addCleanup(named_default.unregister, "test_unregister")
        self.assertIsNot(old, new)
        self.assertEqual(old.value, 1)
        self.assertEqual(new.value, 2)

    @unittest.skipUnless(sys.version_info >= (3, 12), "PEP 695 syntax")
    def test_generic_type_parameters(self):
        namespace = {"dynamic_default_args": dynamic_default_args, "default": default}
        exec("@dynamic_default_args\ndef f[T](x: T = default(1)) -> T: return x", namespace)
        f = namespace["f"]
        self.assertEqual(f(), 1)
        self.assertEqual(f.__type_params__, f.__wrapped__.__type_params__)

    @unittest.skipUnless(sys.version_info >= (3, 14), "PEP 649 lazy annotations")
    def test_lazy_annotations_are_not_evaluated_during_decoration(self):
        namespace = {"dynamic_default_args": dynamic_default_args, "default": default,
                     "calls": []}
        # compile() avoids inheriting this test module's annotation behavior.
        exec(compile("@dynamic_default_args\ndef f(x: calls.append(1) or Later = default(1)) -> Later: return x\nclass Later: pass",
                     "<lazy annotation test>", "exec", dont_inherit=True), namespace)
        f = namespace["f"]
        self.assertEqual(namespace["calls"], [])
        self.assertEqual(f(), 1)
        self.assertIs(inspect.signature(f).return_annotation, namespace["Later"])
        self.assertIs(f.__annotations__["x"], namespace["Later"])

    def test_bound_method_with_explicit_signature(self):
        class C:
            def f(self, x):
                return x

        signature = inspect.Signature([
            inspect.Parameter("x", inspect.Parameter.POSITIONAL_ONLY, default=default(3))])
        wrapped = dynamic_default_args(signature=signature)(C().f)
        self.assertEqual(wrapped(), 3)


class AsyncDefaultsTest(unittest.IsolatedAsyncioTestCase):
    async def test_async_callable_instance(self):
        class C:
            async def __call__(self, x=default(2)):
                return x

        wrapped = dynamic_default_args()(C())
        self.assertTrue(inspect.iscoroutinefunction(wrapped))
        self.assertEqual(await wrapped(), 2)

    async def test_coroutine_identity_and_resolution_timing(self):
        cell = default(1)

        @dynamic_default_args
        async def f(x=cell):
            return x

        self.assertTrue(inspect.iscoroutinefunction(f))
        pending = f()
        cell.value = 2
        self.assertEqual(await pending, 2)
        self.assertIsNone(await f(None))
        with self.assertRaises(TypeError):
            default_factory(f)

    async def test_async_generator_send_throw_close(self):
        closed = []

        @dynamic_default_args
        async def f(x=default(1)):
            try:
                sent = yield x
                try:
                    yield sent
                except LookupError:
                    yield 99
            finally:
                closed.append(True)

        self.assertTrue(inspect.isasyncgenfunction(f))
        iterator = f()
        self.assertEqual(await anext(iterator), 1)
        self.assertEqual(await iterator.asend(7), 7)
        self.assertEqual(await iterator.athrow(LookupError()), 99)
        await iterator.aclose()
        self.assertEqual(closed, [True])
        self.assertEqual([item async for item in f()], [1, None])

    async def test_empty_and_failing_async_generator(self):
        @dynamic_default_args
        async def empty(x=default(1)):
            if False:
                yield x

        self.assertEqual([x async for x in empty()], [])

        @dynamic_default_args
        async def fail(x=default(1)):
            yield x
            raise RuntimeError("boom")

        iterator = fail()
        await anext(iterator)
        with self.assertRaisesRegex(RuntimeError, "boom"):
            await anext(iterator)


class GeneratorDefaultsTest(unittest.TestCase):
    def test_generator_protocol(self):
        closed = []

        @dynamic_default_args
        def f(x=default(1)):
            try:
                sent = yield x
                try:
                    yield sent
                except LookupError:
                    yield 99
                return 123
            finally:
                closed.append(True)

        self.assertTrue(inspect.isgeneratorfunction(f))
        iterator = f()
        self.assertEqual(next(iterator), 1)
        self.assertEqual(iterator.send(7), 7)
        self.assertEqual(iterator.throw(LookupError()), 99)
        with self.assertRaises(StopIteration) as end:
            next(iterator)
        self.assertEqual(end.exception.value, 123)
        self.assertEqual(closed, [True])
        iterator = f()
        next(iterator)
        iterator.close()
        self.assertEqual(closed, [True, True])
