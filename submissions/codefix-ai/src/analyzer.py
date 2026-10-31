"""
CodeFix AI — Deterministic Python AST Static Analyzer Module

This module inspects source code statically using Python's built-in `ast` module
and compilation checks WITHOUT executing the code on the host machine.
It identifies syntax errors, suspicious constructs, anti-patterns, and provides
actionable diagnostic suggestions.
"""

import ast
from typing import Dict, Any, List, Optional


# Python built-in names that should generally not be shadowed
COMMON_BUILTIN_SHADOWS = {
    "list", "dict", "set", "tuple", "str", "int", "float", "bool",
    "type", "id", "input", "min", "max", "sum", "range", "open",
    "filter", "map", "all", "any", "dir", "len"
}


class CodeIssue:
    """Represents a diagnostic issue detected during static analysis."""
    def __init__(self, issue_type: str, message: str, line: Optional[int] = None,
                 col: Optional[int] = None, suggestion: Optional[str] = None):
        self.issue_type = issue_type      # 'syntax_error', 'warning', 'anti_pattern'
        self.message = message
        self.line = line
        self.col = col
        self.suggestion = suggestion

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.issue_type,
            "message": self.message,
            "line": self.line,
            "col": self.col,
            "suggestion": self.suggestion
        }


class PythonASTVisitor(ast.NodeVisitor):
    """
    AST Visitor to detect common static defects, bugs, and style issues in Python code.
    Runs entirely statically without code execution.
    """

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.lines = source_code.splitlines()
        self.warnings: List[CodeIssue] = []
        self.defined_functions = set()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # 1. Check for duplicate function definitions in same scope
        if node.name in self.defined_functions:
            self.warnings.append(CodeIssue(
                issue_type="warning",
                message=f"Duplicate function definition: '{node.name}' was already defined previously.",
                line=node.lineno,
                col=node.col_offset,
                suggestion="Rename the duplicate function or remove redundant declarations."
            ))
        else:
            self.defined_functions.add(node.name)

        # 2. Check for shadowing built-in names
        if node.name in COMMON_BUILTIN_SHADOWS:
            self.warnings.append(CodeIssue(
                issue_type="warning",
                message=f"Function name '{node.name}' shadows Python built-in standard library function.",
                line=node.lineno,
                col=node.col_offset,
                suggestion=f"Consider renaming '{node.name}' to a more descriptive domain-specific name."
            ))

        # 3. Detect mutable default arguments: def func(items=[]) or def func(opts={})
        num_args = len(node.args.args)
        num_defaults = len(node.args.defaults)
        default_offset = num_args - num_defaults

        for i, default in enumerate(node.args.defaults):
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                param_name = node.args.args[default_offset + i].arg if (default_offset + i) < num_args else "argument"
                type_name = "list" if isinstance(default, ast.List) else ("dict" if isinstance(default, ast.Dict) else "set")
                self.warnings.append(CodeIssue(
                    issue_type="anti_pattern",
                    message=f"Mutable default argument ({type_name}) detected for parameter '{param_name}' in function '{node.name}'.",
                    line=default.lineno,
                    col=default.col_offset,
                    suggestion=f"Mutable defaults retain state across function calls. Change to '{param_name}=None' and initialize inside function: 'if {param_name} is None: {param_name} = []'."
                ))

        for param, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            if default is not None and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                type_name = "list" if isinstance(default, ast.List) else ("dict" if isinstance(default, ast.Dict) else "set")
                self.warnings.append(CodeIssue(
                    issue_type="anti_pattern",
                    message=f"Mutable default argument ({type_name}) detected for keyword-only parameter '{param.arg}' in function '{node.name}'.",
                    line=default.lineno,
                    col=default.col_offset,
                    suggestion=f"Mutable defaults retain state across function calls. Change to '{param.arg}=None' and initialize inside function: 'if {param.arg} is None: {param.arg} = []'."
                ))

        # 4. Check for unreachable code after return or raise
        self._check_unreachable_code(node.body)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)  # Apply same checks to async functions

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # Detect bare except clauses: except: (catches SystemExit and KeyboardInterrupt)
        if node.type is None:
            self.warnings.append(CodeIssue(
                issue_type="anti_pattern",
                message="Bare 'except:' clause caught all exceptions including KeyboardInterrupt and SystemExit.",
                line=node.lineno,
                col=node.col_offset,
                suggestion="Catch explicit exceptions like 'except Exception:' or specify the expected error types (e.g. ValueError, KeyError)."
            ))
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare):
        # Detect comparison to None using '==' or '!=' instead of 'is' or 'is not'
        for comparator, op in zip(node.comparators, node.ops):
            if isinstance(comparator, ast.Constant) and comparator.value is None:
                if isinstance(op, (ast.Eq, ast.NotEq)):
                    op_symbol = "==" if isinstance(op, ast.Eq) else "!="
                    suggested = "is None" if isinstance(op, ast.Eq) else "is not None"
                    self.warnings.append(CodeIssue(
                        issue_type="warning",
                        message=f"Comparison to None using '{op_symbol}'. PEP 8 recommends '{suggested}'.",
                        line=node.lineno,
                        col=node.col_offset,
                        suggestion=f"Replace '{op_symbol} None' with '{suggested}' for identity comparison."
                    ))

            # Detect comparison to boolean constants: if x == True
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, bool):
                if isinstance(op, (ast.Eq, ast.NotEq)):
                    self.warnings.append(CodeIssue(
                        issue_type="warning",
                        message=f"Direct comparison to boolean constant '{comparator.value}'.",
                        line=node.lineno,
                        col=node.col_offset,
                        suggestion="Evaluate the truth value directly: 'if condition:' or 'if not condition:'."
                    ))

        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        # Detect static division by literal zero: x / 0, x // 0, x % 0
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self.warnings.append(CodeIssue(
                    issue_type="warning",
                    message="Static division or modulo by literal zero detected. Guaranteed to raise ZeroDivisionError at runtime.",
                    line=node.lineno,
                    col=node.col_offset,
                    suggestion="Add a guard condition to ensure the denominator is non-zero before dividing."
                ))
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert):
        # Detect assert (condition, message) tuple gotcha: in Python, non-empty tuple is always True!
        if isinstance(node.test, ast.Tuple) and len(node.test.elts) > 0:
            self.warnings.append(CodeIssue(
                issue_type="warning",
                message="Assert test is a non-empty tuple, which always evaluates to True in Python.",
                line=node.lineno,
                col=node.col_offset,
                suggestion="Use 'assert condition, message' instead of wrapping them in parentheses: 'assert (cond, msg)'."
            ))
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        # Check for while True: without any break, return, or raise in direct body
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            has_exit = self._has_loop_exit(node.body)
            if not has_exit:
                self.warnings.append(CodeIssue(
                    issue_type="warning",
                    message="'while True' loop contains no detectable break, return, or raise statements.",
                    line=node.lineno,
                    col=node.col_offset,
                    suggestion="Ensure the loop has a termination condition with 'break' or 'return' to avoid infinite execution."
                ))
        self.generic_visit(node)

    def _check_unreachable_code(self, statements: List[ast.stmt]):
        """Detect statements appearing after terminal statements in a block."""
        terminal_seen = False
        terminal_line = 0
        terminal_type = ""

        for stmt in statements:
            if terminal_seen:
                self.warnings.append(CodeIssue(
                    issue_type="warning",
                    message=f"Unreachable code detected after '{terminal_type}' at line {terminal_line}.",
                    line=stmt.lineno,
                    col=stmt.col_offset,
                    suggestion="Remove or refactor dead code located after terminal statements."
                ))
                break

            if isinstance(stmt, (ast.Return, ast.Raise)):
                terminal_seen = True
                terminal_line = stmt.lineno
                terminal_type = "return" if isinstance(stmt, ast.Return) else "raise"

    def _has_loop_exit(self, statements: List[ast.stmt]) -> bool:
        """Recursively check whether a list of statements contains a break, return, or raise."""
        for stmt in statements:
            if isinstance(stmt, (ast.Break, ast.Return, ast.Raise)):
                return True
            if isinstance(stmt, ast.If):
                if self._has_loop_exit(stmt.body) or self._has_loop_exit(stmt.orelse):
                    return True
            if isinstance(stmt, ast.Try):
                if self._has_loop_exit(stmt.body) or any(self._has_loop_exit(h.body) for h in stmt.handlers):
                    return True
        return False


def analyze_python_code(source_code: str) -> Dict[str, Any]:
    """
    Perform comprehensive static AST analysis and syntax checking on Python source code.
    Returns structured diagnostic results.
    """
    if not source_code or not source_code.strip():
        return {
            "language": "python",
            "is_valid_syntax": False,
            "has_warnings": False,
            "syntax_error": None,
            "warnings": [],
            "diagnostics": ["Source code is empty."],
            "summary": "No code provided for static analysis."
        }

    # 1. Parse and compile check for syntax errors
    try:
        parsed_tree = ast.parse(source_code)
    except SyntaxError as e:
        # Extract syntax error location & snippet
        line_num = e.lineno
        col_offset = e.offset
        error_msg = e.msg
        line_text = e.text.strip() if e.text else ""

        suggestion = "Review the syntax near the reported line. Ensure matching parentheses, brackets, quotes, and required colons."
        if "expected ':'" in error_msg:
            suggestion = "Add a colon ':' at the end of the header statement (if, for, while, def, class, etc.)."
        elif "unexpected EOF" in error_msg:
            suggestion = "Check for unclosed parentheses, brackets, or multiline strings that were not terminated."
        elif "unmatched" in error_msg or "was never closed" in error_msg:
            suggestion = "Verify that all brackets, braces, and parentheses are properly matched and closed."

        diagnostics = [
            f"SyntaxError at line {line_num}, col {col_offset}: {error_msg}",
            f"Code: {line_text}" if line_text else "",
            f"Suggestion: {suggestion}"
        ]
        diagnostics = [d for d in diagnostics if d]

        return {
            "language": "python",
            "is_valid_syntax": False,
            "has_warnings": False,
            "syntax_error": {
                "message": error_msg,
                "line": line_num,
                "col": col_offset,
                "snippet": line_text,
                "suggestion": suggestion
            },
            "warnings": [],
            "diagnostics": diagnostics,
            "summary": f"Python Syntax Error detected at line {line_num}: {error_msg}."
        }
    except Exception as e:
        return {
            "language": "python",
            "is_valid_syntax": False,
            "has_warnings": False,
            "syntax_error": {
                "message": str(e),
                "line": None,
                "col": None,
                "snippet": "",
                "suggestion": "Review submitted code structure."
            },
            "warnings": [],
            "diagnostics": [f"Parsing error: {str(e)}"],
            "summary": f"Could not parse Python code: {str(e)}"
        }

    # 2. Syntax is valid; walk AST to find anti-patterns, suspicious constructs, and warnings
    visitor = PythonASTVisitor(source_code)
    visitor.visit(parsed_tree)

    formatted_diagnostics = []
    if visitor.warnings:
        for w in visitor.warnings:
            loc = f"Line {w.line}: " if w.line else ""
            formatted_diagnostics.append(f"[{w.issue_type.upper()}] {loc}{w.message} -> {w.suggestion}")
    else:
        formatted_diagnostics.append("✓ Python syntax is valid. No suspicious static anti-patterns detected.")

    summary = (
        f"Syntax check passed with {len(visitor.warnings)} static diagnostic warning(s)."
        if visitor.warnings
        else "Syntax check passed cleanly with zero static warnings."
    )

    return {
        "language": "python",
        "is_valid_syntax": True,
        "has_warnings": len(visitor.warnings) > 0,
        "syntax_error": None,
        "warnings": [w.to_dict() for w in visitor.warnings],
        "diagnostics": formatted_diagnostics,
        "summary": summary
    }


def analyze_code(source_code: str, language: str) -> Dict[str, Any]:
    """
    Main dispatch function for static analysis.
    Distinguishes Python AST checking from non-Python languages.
    """
    lang = (language or "python").lower()

    if lang == "python":
        return analyze_python_code(source_code)

    # For non-Python languages, state clearly that Python AST does not apply
    return {
        "language": lang,
        "is_valid_syntax": True,
        "has_warnings": False,
        "syntax_error": None,
        "warnings": [],
        "diagnostics": [
            f"Deterministic AST parser is configured for Python. Static parsing for {lang.capitalize()} requires native toolchain tools.",
            f"AI agent semantic debugging will inspect this {lang.capitalize()} code for logical and structural bugs."
        ],
        "summary": f"Static AST checks bypassed for {lang.capitalize()}. AI semantic inspection active."
    }
