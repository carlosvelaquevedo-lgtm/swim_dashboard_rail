"""Fail when the Railway app imports a GPU library at module scope.

Torch, transformers, and modal may be imported inside a function, and anywhere
under modal_3d/ or tests/. MediaPipe is allowed only in pages/2_Dashboard.py.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANNED = {"torch", "transformers", "modal"}
SKIP_PARTS = {"modal_3d", "tests", "__pycache__", ".git"}
ALLOWED_MEDIAPIPE = "pages/2_Dashboard.py"


def _imports(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
        return
    if isinstance(node, ast.Import):
        for alias in node.names:
            yield node.lineno, alias.name.split(".")[0]
        return
    if isinstance(node, ast.ImportFrom):
        if node.module:
            yield node.lineno, node.module.split(".")[0]
        return
    for child in ast.iter_child_nodes(node):
        yield from _imports(child)


def main():
    failures = []
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            failures.append(f"{rel.as_posix()}:{exc.lineno} {exc.msg}")
            continue
        for lineno, name in _imports(tree):
            if name in BANNED:
                failures.append(f"{rel.as_posix()}:{lineno} top-level import of {name}")
            if name == "mediapipe" and rel.as_posix() != ALLOWED_MEDIAPIPE:
                failures.append(
                    f"{rel.as_posix()}:{lineno} mediapipe is allowed only in {ALLOWED_MEDIAPIPE}"
                )
    if failures:
        print("\n".join(failures))
        return 1
    print("import guard ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
