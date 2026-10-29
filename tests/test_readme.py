"""Keep the README's Python snippets executable as one walkthrough."""
from pathlib import Path
import re
import unittest


class ReadmeExamplesTest(unittest.TestCase):
    def test_python_walkthrough(self):
        path = Path(__file__).resolve().parents[1] / "README.md"
        source = path.read_text(encoding="utf-8")
        namespace = {"__name__": "readme_examples"}
        for index, match in enumerate(re.finditer(r"^```python\n(.*?)^```", source,
                                                  flags=re.MULTILINE | re.DOTALL), 1):
            with self.subTest(block=index):
                padding = "\n" * source[:match.start(1)].count("\n")
                exec(compile(padding + match.group(1), str(path), "exec"), namespace)
