"""Owner's report 2026-09-09: `mike --version` on another machine died at import with
`NameError: name 'Dict' is not defined` (commands.py, `_blocking`). Python 3.14 evaluates
annotations lazily (PEP 649), so a typing name missing from the import is invisible where the
tests run; Python ≤ 3.13 evaluates them at `def` time and refuses to import the module at all.
This test evaluates every annotation on every version, so the gap cannot open again."""
import importlib
import inspect
import pkgutil
import typing
import unittest

import mike


class Annotations(unittest.TestCase):
    def test_every_annotation_resolves_on_every_python(self):
        failures = []
        for info in pkgutil.iter_modules(mike.__path__):
            if info.name == "__main__":
                continue  # importing it runs main() on unittest's argv
            mod = importlib.import_module(f"mike.{info.name}")
            for name, obj in inspect.getmembers(mod):
                if getattr(obj, "__module__", None) != mod.__name__:
                    continue
                targets = [(name, obj)] if inspect.isfunction(obj) else []
                if inspect.isclass(obj):
                    targets += [(f"{name}.{n}", f) for n, f in inspect.getmembers(obj, inspect.isfunction)
                                if f.__module__ == mod.__name__]
                    targets.append((name, obj))
                for label, target in targets:
                    try:
                        typing.get_type_hints(target)
                    except NameError as e:
                        failures.append(f"{mod.__name__}.{label}: {e}")
        self.assertEqual(failures, [], "a typing name used in an annotation is not imported")
