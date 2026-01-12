import ast
import sys
from pathlib import Path
from typing import Set, List, Tuple

# Configuration
ROOT_DIR = Path(__file__).parent.resolve()
PACKAGE_NAME = "paas"
OUTPUT_FILE = ROOT_DIR / "submission.py"


def find_imports(file_path: Path) -> List[Tuple[str, int]]:
    """
    Parses a python file and returns a list of (module_name, level)
    for internal imports.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(file_path))

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # We only care if it starts with the package name
                if alias.name.startswith(PACKAGE_NAME):
                    imports.append((alias.name, 0))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(PACKAGE_NAME):
                imports.append((node.module, 0))
            elif node.level > 0:
                # Relative import
                imports.append((node.module, node.level))
    return imports


def resolve_module(current_file: Path, module_name: str, level: int) -> Path:
    """
    Resolves a module import to a file path.
    """
    if level == 0:
        # Absolute import e.g. paas.models
        parts = module_name.split(".")
        # parts[0] is 'paas', which maps to ROOT_DIR/paas
        rel_parts = parts[1:]
        candidate = ROOT_DIR / "paas" / Path(*rel_parts)
    else:
        # Relative import
        # . -> level 1, .. -> level 2
        # current_file is e.g. paas/parser.py
        # parent is paas/
        current_dir = current_file.parent
        for _ in range(level - 1):
            current_dir = current_dir.parent

        if module_name:
            candidate = current_dir / Path(*module_name.split("."))
        else:
            candidate = current_dir

    # Check for .py or package
    if candidate.with_suffix(".py").exists():
        return candidate.with_suffix(".py")
    if (candidate / "__init__.py").exists():
        return candidate / "__init__.py"

    raise FileNotFoundError(
        f"Could not resolve module {module_name} (level {level}) from {current_file}"
    )


def get_dependencies(file_path: Path) -> List[Path]:
    deps = []
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(file_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PACKAGE_NAME):
                    deps.append(resolve_module(file_path, alias.name, 0))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(PACKAGE_NAME):
                deps.append(resolve_module(file_path, node.module, 0))
            elif node.level > 0:
                deps.append(resolve_module(file_path, node.module, node.level))

    return list(set(deps))


def topological_sort(entry_point: Path) -> List[Path]:
    visited = set()
    order = []

    def visit(path: Path):
        if path in visited:
            return
        visited.add(path)
        try:
            deps = get_dependencies(path)
            # Sort deps to ensure deterministic order
            deps.sort()
            for dep in deps:
                visit(dep)
            order.append(path)
        except FileNotFoundError as e:
            print(f"Warning: {e}")

    visit(entry_point)
    return order


def is_main_check(node: ast.AST) -> bool:
    """
    Checks if an AST node is 'if __name__ == "__main__":'
    """
    if not isinstance(node, ast.If):
        return False

    # Check compare
    test = node.test
    if not isinstance(test, ast.Compare):
        return False

    # Check left side: __name__
    if not (isinstance(test.left, ast.Name) and test.left.id == "__name__"):
        return False

    # Check ops: ==
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False

    # Check comparators: "__main__"
    if len(test.comparators) != 1:
        return False

    comp = test.comparators[0]
    if isinstance(comp, ast.Constant) and comp.value == "__main__":
        return True
    if isinstance(comp, ast.Str) and comp.s == "__main__":  # Legacy Python
        return True

    return False


def clean_content(file_path: Path, keep_main: bool) -> str:
    """
    Reads file content and removes internal imports.
    Also removes 'if __name__ == "__main__":' block if keep_main is False.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)
    lines = content.splitlines(keepends=True)

    # Identify lines to remove
    lines_to_skip = set()

    # 1. Imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PACKAGE_NAME):
                    # Remove the whole import statement
                    for lineno in range(node.lineno - 1, node.end_lineno):
                        lines_to_skip.add(lineno)
        elif isinstance(node, ast.ImportFrom):
            if (node.module and node.module.startswith(PACKAGE_NAME)) or node.level > 0:
                for lineno in range(node.lineno - 1, node.end_lineno):
                    lines_to_skip.add(lineno)

    # 2. Main block
    if not keep_main:
        for node in ast.walk(tree):
            if is_main_check(node):
                for lineno in range(node.lineno - 1, node.end_lineno):
                    lines_to_skip.add(lineno)

    output = []
    for i, line in enumerate(lines):
        if i not in lines_to_skip:
            output.append(line)

    return "".join(output)


def collect_stdlib_imports(files: List[Path]) -> Set[str]:
    imports = set()
    for p in files:
        with open(p, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if not alias.name.startswith(PACKAGE_NAME):
                                if alias.asname:
                                    imports.add(
                                        f"import {alias.name} as {alias.asname}"
                                    )
                                else:
                                    imports.add(f"import {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        if (
                            not (node.module and node.module.startswith(PACKAGE_NAME))
                            and node.level == 0
                        ):
                            names = ", ".join(
                                [
                                    f"{n.name} as {n.asname}" if n.asname else n.name
                                    for n in node.names
                                ]
                            )
                            imports.add(f"from {node.module} import {names}")
            except Exception as e:
                print(f"Error parsing imports from {p}: {e}")
    return imports


def main():
    if len(sys.argv) < 2:
        print("Usage: python bundle.py <entry_point>")
        sys.exit(1)

    entry_point = Path(sys.argv[1]).resolve()
    if not entry_point.exists():
        print(f"Entry point {entry_point} not found")
        sys.exit(1)

    print(f"Bundling starting from {entry_point}")

    files = topological_sort(entry_point)
    print(f"Found {len(files)} files in dependency order:")
    for f in files:
        print(f"  {f.relative_to(ROOT_DIR)}")

    stdlib_imports = collect_stdlib_imports(files)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write("# MERGED SUBMISSION FILE\n")
        out.write("# Generated by bundle.py\n\n")

        # Write stdlib imports
        sorted_imports = sorted(list(stdlib_imports))
        for imp in sorted_imports:
            out.write(imp + "\n")
        out.write("\n")

        # Write file contents
        for f in files:
            out.write(f"# --- {f.relative_to(ROOT_DIR)} ---\n")
            # Only keep main block for the entry point
            keep_main = f == entry_point
            content = clean_content(f, keep_main=keep_main)
            out.write(content)
            out.write("\n\n")

    print(f"Wrote merged file to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
