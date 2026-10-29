"""Optional compiled integration tests. Set DDA_TEST_CYTHON=1 to require them."""
import importlib
import inspect
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def build_fixture():
    from Cython.Build import cythonize
    from setuptools import Distribution, Extension

    output = ROOT / "develop" / "test-build" / sys.implementation.cache_tag
    extensions = cythonize(
        [Extension("_dda_cython_fixture", [str(ROOT / "tests" / "cython" / "fixtures.pyx")])],
        compiler_directives={"language_level": 3, "binding": True},
        build_dir=str(output / "generated"), quiet=True,
    )
    distribution = Distribution({"ext_modules": extensions})
    command = distribution.get_command_obj("build_ext")
    command.build_lib = str(output)
    command.build_temp = str(output / "temp")
    distribution.run_command("build_ext")
    return output


class CythonIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DDA_TEST_CYTHON"):
            raise unittest.SkipTest("Set DDA_TEST_CYTHON=1 for compiled integration tests")
        # Build failures must fail the integration job, rather than being skipped.
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--build"],
                                cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        output = ROOT / "develop" / "test-build" / sys.implementation.cache_tag
        sys.path.insert(0, str(output))
        cls.addClassCleanup(sys.path.remove, str(output))
        cls.module = importlib.import_module("_dda_cython_fixture")

    def setUp(self):
        self.module.cell.value = 1.0

    def test_def_and_typed_def(self):
        self.assertEqual(self.module.untyped(), 1.0)
        self.assertEqual(self.module.typed(), 1.0)
        self.module.cell.value = 2.5
        self.assertEqual(self.module.untyped(), 2.5)
        self.assertEqual(self.module.typed(), 2.5)
        self.assertEqual(self.module.typed(8), 8.0)
        with self.assertRaises(TypeError):
            self.module.typed(None)

    def test_annotation_type_inference(self):
        self.assertEqual(self.module.annotated(), 3.5)
        self.assertEqual(self.module.annotated(2), 2.0)

    def test_cpdef_python_wrapper_and_native_boundary(self):
        self.assertEqual(self.module.wrapped_dual(), 1.0)
        self.module.cell.value = 4.5
        self.assertEqual(self.module.wrapped_dual(), 4.5)
        self.assertEqual(self.module.native_call(), 0.0)
        self.assertEqual(self.module.dual(), 0.0)

    def test_methods(self):
        from dynamic_default_args import dynamic_default_args

        self.assertEqual(self.module.PythonClass().method(), 1.0)
        bound = self.module.ExtensionClass().method
        wrapped = dynamic_default_args(defaults={"x": self.module.cell})(bound)
        self.module.cell.value = 6.5
        self.assertEqual(wrapped(), 6.5)
        self.assertIn("x", inspect.signature(wrapped).parameters)


if __name__ == "__main__" and "--build" in sys.argv:
    build_fixture()
