#!/usr/bin/env python3
"""Fail if the engine imports anything outside the standard library.

The engine is deliberately dependency-free: the only third-party code lives in
the optional web layer (``server.py``, behind the ``web`` extra) and in
deferred imports guarded by ``try/except ImportError``. That is a promise to
users, so it is enforced rather than documented.

Only imports that execute *when the module is imported* count. An import
inside a function, or inside a ``try`` that catches ImportError, is the
standard way to make a dependency optional and is allowed.

    python3 tools/check_stdlib_only.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "src" / "bindsmith"

#: Modules exempt from the check: the optional web layer needs FastAPI.
EXEMPT = {"server.py"}

#: First-party packages (this project's own modules).
OWN = {"bindsmith"}

#: Exceptions that mark an import as optional rather than required.
SOFT = {"ImportError", "ModuleNotFoundError"}

#: Compound statements whose bodies run at import time.
RUNTIME_BLOCKS = (ast.If, ast.Try, ast.With, ast.AsyncWith)


def _guarded(node: ast.Try) -> bool:
    """True for a try/except ImportError — the optional-dependency idiom."""
    for handler in node.handlers:
        names = {getattr(t, "id", None) or getattr(t, "attr", None)
                 for t in [handler.type] if t is not None}
        if names & SOFT or handler.type is None:
            return True
    return False


def _import_time_imports(body: list[ast.stmt], guarded: bool = False):
    """Yield (module_name, is_guarded) for imports that run at import time."""
    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                yield (node.module or "").split(".")[0], guarded
            else:
                for a in node.names:
                    yield a.name.split(".")[0], guarded
        elif isinstance(node, RUNTIME_BLOCKS):
            inner_guarded = guarded or (isinstance(node, ast.Try) and _guarded(node))
            yield from _import_time_imports(node.body, inner_guarded)
            for handler in getattr(node, "handlers", []):
                yield from _import_time_imports(handler.body, guarded)
        # deliberately not descending into FunctionDef / ClassDef


def main() -> int:
    stdlib = set(sys.stdlib_module_names)
    problems: list[str] = []
    checked = 0

    for f in sorted(ENGINE.glob("*.py")):
        if f.name in EXEMPT:
            continue
        checked += 1
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for mod, guarded in _import_time_imports(tree.body):
            if not mod or guarded or mod in stdlib or mod in OWN:
                continue
            problems.append(f"{f.name}: imports {mod} at import time")

    if problems:
        print("engine imports non-stdlib modules:")
        for p in problems:
            print("  " + p)
        return 1

    print(f"engine is standard library only ({checked} modules checked, "
          f"{len(EXEMPT)} exempt: {', '.join(sorted(EXEMPT))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
