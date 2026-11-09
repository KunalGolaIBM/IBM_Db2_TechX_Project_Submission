"""
GitMind — Code Analysis Tools (Tree-sitter)

Provides function-level and class-level AST analysis of source files.
Detects which functions/classes changed in a commit, traces function
history through commits, and extracts dependency (import) information.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from git import Repo, BadName
from langchain.tools import tool

#  TREE-SITTER SETUP

# Language → (tree-sitter module, file extensions)
_LANGUAGE_MAP = {
    "python": ("tree_sitter_python", [".py"]),
    "javascript": ("tree_sitter_javascript", [".js", ".jsx", ".mjs"]),
    "typescript": ("tree_sitter_typescript", [".ts", ".tsx"]),
}

# Node types that represent function/class definitions per language
_DEFINITION_QUERIES = {
    "python": {
        "functions": ["function_definition"],
        "classes": ["class_definition"],
        "name_field": "name",
    },
    "javascript": {
        "functions": ["function_declaration", "arrow_function", "method_definition"],
        "classes": ["class_declaration"],
        "name_field": "name",
    },
    "typescript": {
        "functions": ["function_declaration", "arrow_function", "method_definition"],
        "classes": ["class_declaration"],
        "name_field": "name",
    },
}


def _detect_language(file_path: str) -> Optional[str]:
    """Detect programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    for lang, (_, extensions) in _LANGUAGE_MAP.items():
        if ext in extensions:
            return lang
    return None


def _get_parser(language: str):
    """Get a tree-sitter parser for the given language."""
    import tree_sitter

    if language == "python":
        import tree_sitter_python as tsp
        lang = tree_sitter.Language(tsp.language())
    elif language == "javascript":
        import tree_sitter_javascript as tsjs
        lang = tree_sitter.Language(tsjs.language())
    elif language == "typescript":
        import tree_sitter_typescript as tsts
        lang = tree_sitter.Language(tsts.language_typescript())
    else:
        return None

    parser = tree_sitter.Parser(lang)
    return parser


def _extract_definitions(source_bytes: bytes, language: str) -> list[dict]:
    """
    Parse source code and extract function/class definitions.
    Returns a list of dicts with name, type, start_line, end_line.
    """
    parser = _get_parser(language)
    if not parser:
        return []

    tree = parser.parse(source_bytes)

    query_info = _DEFINITION_QUERIES.get(language)
    if not query_info:
        return []

    definitions = []
    func_types = set(query_info["functions"])
    class_types = set(query_info["classes"])

    def _walk(node, parent_class=None):
        node_type = node.type

        if node_type in func_types:
            name_node = node.child_by_field_name(query_info["name_field"])
            name = name_node.text.decode("utf-8") if name_node else "<anonymous>"

            # Check for decorators (Python)
            decorators = []
            if language == "python" and node.parent and node.parent.type == "decorated_definition":
                for child in node.parent.children:
                    if child.type == "decorator":
                        decorators.append(child.text.decode("utf-8"))

            # Extract parameters
            params = []
            params_node = node.child_by_field_name("parameters")
            if params_node:
                for child in params_node.children:
                    if child.type in ("identifier", "typed_parameter", "default_parameter"):
                        params.append(child.text.decode("utf-8"))

            # Extract docstring (Python)
            docstring = None
            if language == "python":
                body = node.child_by_field_name("body")
                if body and body.child_count > 0:
                    first_stmt = body.children[0]
                    if first_stmt.type == "expression_statement":
                        expr = first_stmt.children[0] if first_stmt.child_count > 0 else None
                        if expr and expr.type == "string":
                            docstring = expr.text.decode("utf-8").strip("\"'")[:200]

            full_name = f"{parent_class}.{name}" if parent_class else name
            definitions.append({
                "name": full_name,
                "type": "function" if node_type in func_types else "class",
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "parameters": params,
                "decorators": decorators,
                "docstring": docstring,
            })

        elif node_type in class_types:
            name_node = node.child_by_field_name(query_info["name_field"])
            name = name_node.text.decode("utf-8") if name_node else "<anonymous>"

            definitions.append({
                "name": name,
                "type": "class",
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "parameters": [],
                "decorators": [],
                "docstring": None,
            })

            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    _walk(child, parent_class=name)
            return

        for child in node.children:
            _walk(child, parent_class)

    _walk(tree.root_node)
    return definitions


def _extract_imports(source_bytes: bytes, language: str) -> list[str]:
    """Extract import statements from source code."""
    parser = _get_parser(language)
    if not parser:
        return []

    tree = parser.parse(source_bytes)
    imports = []

    def _walk(node):
        if language == "python" and node.type in ("import_statement", "import_from_statement"):
            imports.append(node.text.decode("utf-8"))
        elif language in ("javascript", "typescript") and node.type == "import_statement":
            imports.append(node.text.decode("utf-8"))

        for child in node.children:
            _walk(child)

    _walk(tree.root_node)
    return imports


#  LANGCHAIN TOOLS


@tool
def analyze_file_ast(file_path: str, repo_path: str = ".") -> str:
    """
    Parse a source file and extract all function/class definitions,
    their line ranges, parameters, decorators, and docstrings.
    Supports Python, JavaScript, and TypeScript.
    """
    language = _detect_language(file_path)
    if not language:
        return f"Unsupported file type for AST analysis: {file_path}"

    full_path = Path(repo_path) / file_path
    if not full_path.exists():
        return f"File not found: {file_path}"

    source = full_path.read_bytes()
    definitions = _extract_definitions(source, language)

    if not definitions:
        return f"No function/class definitions found in {file_path}"

    return str({
        "file": file_path,
        "language": language,
        "definitions": definitions,
        "total_functions": sum(1 for d in definitions if d["type"] == "function"),
        "total_classes": sum(1 for d in definitions if d["type"] == "class"),
    })


@tool
def get_changed_functions(repo_path: str = ".", commit_hash: str = "HEAD") -> str:
    """
    For a given commit, determine which functions/classes were modified
    by comparing the AST of changed files before and after the commit.
    Returns a per-file breakdown of added, removed, and modified functions.
    """
    repo = Repo(Path(repo_path).resolve(), search_parent_directories=True)
    try:
        commit = repo.commit(commit_hash)
    except BadName:
        return f"Invalid commit: {commit_hash}"

    if not commit.parents:
        return "Initial commit — all functions are new."

    parent = commit.parents[0]
    diffs = parent.diff(commit)

    results = []
    for diff in diffs:
        file_path = diff.b_path or diff.a_path
        language = _detect_language(file_path)
        if not language:
            continue

        old_defs = set()
        new_defs = set()

        try:
            if diff.a_blob:
                old_source = diff.a_blob.data_stream.read()
                for d in _extract_definitions(old_source, language):
                    old_defs.add(d["name"])
        except Exception:
            pass

        try:
            if diff.b_blob:
                new_source = diff.b_blob.data_stream.read()
                for d in _extract_definitions(new_source, language):
                    new_defs.add(d["name"])
        except Exception:
            pass

        added = new_defs - old_defs
        removed = old_defs - new_defs
        possibly_modified = old_defs & new_defs

        if added or removed or possibly_modified:
            results.append({
                "file": file_path,
                "language": language,
                "added_functions": list(added),
                "removed_functions": list(removed),
                "potentially_modified": list(possibly_modified),
            })

    if not results:
        return "No function-level changes detected (files may not be supported languages)."

    return str(results)


@tool
def get_function_history(
    repo_path: str = ".",
    function_name: str = "",
    file_path: str = "",
    limit: int = 20,
) -> str:
    """
    Trace the history of a specific function through commits.
    Finds commits where the function was added, modified, or removed.
    """
    language = _detect_language(file_path)
    if not language:
        return f"Unsupported file type: {file_path}"

    repo = Repo(Path(repo_path).resolve(), search_parent_directories=True)
    history = []

    for commit in repo.iter_commits(paths=file_path, max_count=limit):
        try:
            blob = commit.tree / file_path
            source = blob.data_stream.read()
            defs = _extract_definitions(source, language)
            func_names = [d["name"] for d in defs]

            if function_name in func_names:
                func_info = next(d for d in defs if d["name"] == function_name)
                history.append({
                    "commit": commit.hexsha[:8],
                    "date": commit.committed_datetime.isoformat(),
                    "author": commit.author.name,
                    "message": commit.message.strip()[:120],
                    "start_line": func_info["start_line"],
                    "end_line": func_info["end_line"],
                    "status": "present",
                })
            else:
                history.append({
                    "commit": commit.hexsha[:8],
                    "date": commit.committed_datetime.isoformat(),
                    "author": commit.author.name,
                    "message": commit.message.strip()[:120],
                    "status": "not_present",
                })
        except Exception:
            continue

    return str({
        "function": function_name,
        "file": file_path,
        "history": history,
    })


@tool
def analyze_dependencies(file_path: str, repo_path: str = ".") -> str:
    """
    Extract import/dependency information from a source file.
    Shows what modules, packages, and symbols are imported.
    """
    language = _detect_language(file_path)
    if not language:
        return f"Unsupported file type: {file_path}"

    full_path = Path(repo_path) / file_path
    if not full_path.exists():
        return f"File not found: {file_path}"

    source = full_path.read_bytes()
    imports = _extract_imports(source, language)

    return str({
        "file": file_path,
        "language": language,
        "imports": imports,
        "total_imports": len(imports),
    })


# TOOL REGISTRY

CODE_TOOLS = [
    analyze_file_ast,
    get_changed_functions,
    get_function_history,
    analyze_dependencies,
]
