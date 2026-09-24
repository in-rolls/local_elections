import ast

from local_elections.paths import ROOT

SOURCE = ROOT / "src" / "local_elections"
NETWORK_MODULES = {"requests", "httpx", "urllib.request"}


def imports(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def test_parsers_and_validators_are_network_free():
    offenders = []
    for path in sorted((SOURCE / "states").rglob("*.py")):
        if path.name == "harvest.py":
            continue
        imported = imports(ast.parse(path.read_text(encoding="utf-8")))
        forbidden = {
            name
            for name in imported
            if name in NETWORK_MODULES or name == "local_elections.common.fetch"
        }
        if forbidden:
            offenders.append((path.relative_to(ROOT), sorted(forbidden)))
    assert not offenders


def test_every_state_parser_has_a_separate_validator():
    missing = []
    for parser in sorted((SOURCE / "states").glob("*/parse.py")):
        validator = parser.with_name("validate.py")
        if not validator.exists():
            missing.append(parser.parent.name)
    assert not missing


def test_command_entry_points_use_the_shared_lifecycle_logger():
    missing = []
    for path in sorted(SOURCE.rglob("*.py")):
        if path.name == "verify_manifest.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name != "main":
                continue
            names = {
                decorator.func.id
                for decorator in node.decorator_list
                if isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Name)
            }
            if "command" not in names:
                missing.append(path.relative_to(ROOT))
    assert not missing
