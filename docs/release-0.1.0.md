# Version 0.1.0 validation

Local validation completed on Linux x86_64 on 2026-10-29.

| Runtime | Unit and compiled Cython suite | Expected syntax skips |
| --- | --- | --- |
| CPython 3.10.22 | 44 tests, pass | PEP 695 and PEP 649 |
| CPython 3.11.17 | 44 tests, pass | PEP 695 and PEP 649 |
| CPython 3.12.15 | 44 tests, pass | PEP 649 |
| CPython 3.13.16 | 44 tests, pass | PEP 649 |
| CPython 3.14.9 | 44 tests, pass | None |
| CPython 3.15.1 | 44 tests, pass | None |

Cython version: 3.3.0. Compiled tests were required with `DDA_TEST_CYTHON=1`;
compiler failures were not skipped. The system Python 3.12 installation lacked
headers, so a local managed interpreter supplied those headers for its compiled
suite. Test builds and downloaded interpreters are under `develop/`.

The pure Python wheel and source distribution build successfully with
`python -m build --no-isolation`; Twine validates both. The build creates the
wheel from the source archive, exercising that distribution path. Both original
and new Python examples run successfully in the local editable environment.
The wheel was also installed into an isolated environment and its 40 unit tests
passed from outside the checkout (with the expected PEP 649 and optional Cython
skips). Its imported package path was verified to be the installed wheel.
Fresh-environment CI exposed a missing setuptools dependency in the optional
Cython build/test extra; that dependency is now declared explicitly.

The [GitHub Actions workflow](https://github.com/inspiros/dynamic-default-args/actions/workflows/build_wheels.yml)
adds the Linux, Windows, and macOS matrix. Local results above do not establish
Windows/macOS results; consult the workflow run for the release commit.

## Microbenchmark

Best of five runs, 200,000 calls each, CPython 3.13.16 on this machine:

| Call | Omitted argument | Explicit argument |
| --- | ---: | ---: |
| Ordinary function | 15.3 ns | 14.6 ns |
| Manual sentinel check | 40.9 ns | 22.4 ns |
| Generated shared-default wrapper | 60.0 ns | 34.3 ns |
| Generated factory wrapper | 76.2 ns | 39.3 ns |
| Bind the signature each call | 1,486.0 ns | 1,331.9 ns |

These are illustrative small-function costs, not performance guarantees. The
comparison supports generated wrappers over generic per-call binding, while
showing the overhead relative to in-body checks. Reproduce with
`python develop/benchmark.py`.
