from io import StringIO
import ast
import sys
import argparse
from pathlib import Path
from typing import Set, List, Tuple, Dict, Optional

# Configuration
ROOT_DIR = Path(__file__).parent.resolve()
PACKAGE_NAME = "paas"
DEFAULT_OUTPUT_FILE = ROOT_DIR / "submission.py"


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


def resolve_module(current_file: Path, module_name: Optional[str], level: int) -> Path:
    """
    Resolves a module import to a file path.
    """
    if level == 0:
        if not module_name:
            raise ValueError("Absolute import must have a module name")
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

    # It might be a directory without __init__.py (namespace pkg), but purely for file resolution
    # we assume standard packages.
    # Check if it's the package dir itself (e.g. "paas")
    if (
        candidate.exists()
        and candidate.is_dir()
        and (candidate / "__init__.py").exists()
    ):
        return candidate / "__init__.py"

    raise FileNotFoundError(
        f"Could not resolve module {module_name} (level {level}) from {current_file}"
    )


def get_package_exports(init_path: Path) -> Dict[str, Path]:
    """
    Parses an __init__.py file and attempts to map exported names to source files.
    Returns a dict: name -> source_file_path.
    """
    exports = {}
    try:
        with open(init_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(init_path))
    except Exception as e:
        print(f"Warning: Failed to parse {init_path} for exports: {e}")
        return {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # Handle: from .module import Name
            # Handle: from . import module

            # Determine source module path
            try:
                source_path = resolve_module(init_path, node.module, node.level)
            except FileNotFoundError:
                continue

            for alias in node.names:
                name = alias.asname or alias.name
                if alias.name == "*":
                    # Wildcard import re-export - hard to track without parsing source.
                    # Ignore for now, or could map "*" -> source_path (special handling needed)
                    continue

                # If we imported a module (from . import module), then 'module' is the name
                # If we imported a symbol (from .module import Symbol), then 'Symbol' is the name
                # In both cases, source_path points to the file defining it.
                exports[name] = source_path

    return exports


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
            target_path = None
            try:
                if node.module and node.module.startswith(PACKAGE_NAME):
                    target_path = resolve_module(file_path, node.module, 0)
                elif node.level > 0:
                    target_path = resolve_module(file_path, node.module, node.level)
            except FileNotFoundError as e:
                print(f"Warning: {e}")
                continue

            if target_path and target_path.name == "__init__.py":
                # Smart resolution: try to bypass __init__.py if we can find sources for all names
                exports = get_package_exports(target_path)
                resolved_files = set()
                all_resolved = True

                for alias in node.names:
                    if alias.name == "*":
                        all_resolved = False
                        break

                    if alias.name in exports:
                        resolved_files.add(exports[alias.name])
                    else:
                        # Check if alias.name is a submodule (e.g. from paas.middleware import base)
                        # target_path is paas/middleware/__init__.py
                        # Check paas/middleware/base.py
                        possible_submodule = target_path.parent / f"{alias.name}.py"
                        if possible_submodule.exists():
                            resolved_files.add(possible_submodule)
                        else:
                            possible_pkg = (
                                target_path.parent / alias.name / "__init__.py"
                            )
                            if possible_pkg.exists():
                                resolved_files.add(possible_pkg)
                            else:
                                all_resolved = False
                                break

                if all_resolved and resolved_files:
                    deps.extend(list(resolved_files))
                else:
                    # Fallback to including the whole package
                    deps.append(target_path)
            elif target_path:
                deps.append(target_path)

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
            assert node.end_lineno is not None
            for alias in node.names:
                if alias.name.startswith(PACKAGE_NAME):
                    # Remove the whole import statement
                    for lineno in range(node.lineno - 1, node.end_lineno):
                        lines_to_skip.add(lineno)
        elif isinstance(node, ast.ImportFrom):
            assert node.end_lineno is not None
            if (node.module and node.module.startswith(PACKAGE_NAME)) or node.level > 0:
                for lineno in range(node.lineno - 1, node.end_lineno):
                    lines_to_skip.add(lineno)

    # 2. Main block
    if not keep_main:
        for node in ast.walk(tree):
            if is_main_check(node):
                assert hasattr(node, "lineno") and hasattr(node, "end_lineno")
                assert isinstance(node.lineno, int) and isinstance(node.end_lineno, int)
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
    parser = argparse.ArgumentParser(
        description="Bundle the project into a single Python file."
    )
    parser.add_argument(
        "entry_point", help="The entry point script (e.g., paas/main.py)"
    )
    parser.add_argument(
        "--minify", action="store_true", help="Apply minification to the bundled output"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output file path (default: {DEFAULT_OUTPUT_FILE})",
    )
    args = parser.parse_args()

    entry_point = Path(args.entry_point).resolve()
    if not entry_point.exists():
        print(f"Entry point {entry_point} not found")
        sys.exit(1)

    print(f"Bundling starting from {entry_point}")

    files = topological_sort(entry_point)
    print(f"Found {len(files)} files in dependency order:")
    for f in files:
        print(f"  {f.relative_to(ROOT_DIR)}")

    stdlib_imports = collect_stdlib_imports(files)

    # Bundle and write to output
    out = StringIO()
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

    final_content = out.getvalue()

    if args.minify:
        print("Minifying bundled output...")
        try:
            from python_minifier import minify
        except ImportError:
            print(
                "Error: python-minifier not found. Please install it to use --minify."
            )
            sys.exit(1)

        final_content = minify(
            final_content,
            remove_literal_statements=True,
            rename_locals=True,
            combine_imports=True,
            remove_annotations=True,
        )

    with open(args.output, "w", encoding="utf-8") as f_out:
        f_out.write(final_content)

    print(f"Wrote merged file to {args.output}")


if __name__ == "__main__":
    main()
