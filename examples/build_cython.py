"""Build and run the Cython example; generated files stay under develop/."""
import importlib
import os
from pathlib import Path
import shutil
import sys

from Cython.Build import cythonize
from setuptools import Distribution, Extension


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "develop" / "example-build" / sys.implementation.cache_tag
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "examples" / "cython_defaults.pyx", output / "cython_defaults.pyx")
    os.chdir(output)
    extensions = cythonize([Extension("cython_defaults", ["cython_defaults.pyx"])],
                           compiler_directives={"language_level": 3, "binding": True},
                           build_dir="generated", quiet=True)
    distribution = Distribution({"ext_modules": extensions})
    command = distribution.get_command_obj("build_ext")
    command.build_lib = "."
    command.build_temp = "temp"
    distribution.run_command("build_ext")
    sys.path.insert(0, str(output))
    module = importlib.import_module("cython_defaults")
    print("Typed def:", module.compute())
    print("Python wrapper around cpdef:", module.compute_dual())
    print("Native cpdef default:", module.native_compute())
    print("Compiled Python-class method:", module.Client().compute())
    bound = module.bind_client(module.NativeClient())
    print("Bound extension method:", bound())
    module.scale.value = 3.0
    print("After updating scale:", module.compute(), module.compute_dual(), bound())


if __name__ == "__main__":
    main()
