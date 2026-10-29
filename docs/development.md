# Development and releases

## Local setup

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m unittest discover -s tests -v
DDA_TEST_CYTHON=1 .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
```

Windows users can set `DDA_TEST_CYTHON` with PowerShell and use
`.venv\Scripts\python.exe`. No third-party test runner is required.

Runtime code is in `dynamic_default_args/`, durable tests in `tests/`, examples in
`examples/`, documentation in `docs/`, and disposable probes, downloaded
interpreters, benchmarks, and generated extensions in `develop/`.

CI runs the unit and compiled Cython suites on CPython 3.10–3.15 across Linux,
Windows, and macOS. A separate job builds a pure Python wheel and source archive,
then validates their metadata with Twine. Local validation results and remaining
release steps are recorded in [release notes](release-0.1.0.md).

`develop/audit.py` and `develop/audit_cython.py` are observational probes initially
used against 0.0.6; rerunning them against newer code describes the newer behavior.
Use the durable tests as the current compatibility contract. The optional benchmark
in `develop/benchmark.py` compares native calls, an in-body sentinel, generated
wrappers, factories, and generic signature binding. Results depend on the machine.

## Publishing

The version lives in `dynamic_default_args/_version.py`. Review the changelog,
run the checks above, and verify the tag matches that version before release.

The GitHub workflow publishes only version tags after both test and build jobs
succeed. It supports PyPI trusted publishing with the `pypi` GitHub environment.
Configure the PyPI project to trust this repository and workflow file
`.github/workflows/build_wheels.yml` with environment `pypi`. Existing token secrets
are optional: if the repository's existing `pypi_password` secret is available,
the action uses that API token instead. Otherwise, the external trust
configuration must exist before the first automated release.

An authenticated maintainer can alternatively upload the validated `dist/` files
using Twine. Uploading a version to PyPI is permanent; published files cannot be
replaced for the same version. Do not publish artifacts whose supported-platform
CI has not passed.
