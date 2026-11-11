"""Safe process execution and path boundary enforcement."""

import os
import re
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


# Regex patterns to redact secrets before persistence or presentation
SECRET_PATTERNS = [
    (re.compile(r'(?i)(api[_-]?key|secret|token|password|auth|jwt)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.\/+=]{8,})["\']?'), r'\1="[REDACTED_SECRET]"'),
    (re.compile(r'AKIA[0-9A-Z]{16}'), r'[REDACTED_AWS_KEY]'),
    (re.compile(r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC )?PRIVATE KEY-----'), r'[REDACTED_PRIVATE_KEY]'),
    (re.compile(r'ghp_[a-zA-Z0-9]{36}'), r'[REDACTED_GITHUB_PAT]'),
]


def redact_secrets(text: str) -> str:
    """Redact sensitive credentials, tokens, and private keys from strings."""
    if not text:
        return text
    clean = text
    for pattern, repl in SECRET_PATTERNS:
        clean = pattern.sub(repl, clean)
    return clean


class SafeExecutionBoundary:
    """Enforces strict path containment, no shell execution, timeouts, and redaction."""

    def __init__(self, workspace_root: str, max_timeout_seconds: int = 60, max_output_bytes: int = 1_000_000):
        self.workspace_root = Path(workspace_root).resolve()
        self.max_timeout_seconds = max_timeout_seconds
        self.max_output_bytes = max_output_bytes

    def validate_path_containment(self, target_path: str) -> Path:
        """Ensure path does not escape the repository boundary."""
        resolved = (self.workspace_root / target_path).resolve()
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError:
            raise PermissionError(f"Security violation: path traversal outside workspace detected: {target_path}")
        return resolved

    def run_command(
        self,
        cmd_args: List[str],
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        redact: bool = True,
    ) -> Tuple[int, str, str, int]:
        """
        Execute command with typed argument array.
        NEVER uses shell=True. Enforces bounds, timeouts, and output limits.
        Returns: (exit_code, stdout, stderr, duration_ms)
        """
        if not cmd_args or not isinstance(cmd_args, list):
            raise ValueError("Command arguments must be a non-empty list of strings.")

        exec_cwd = str(self.workspace_root)
        if cwd:
            validated_cwd = self.validate_path_containment(cwd)
            exec_cwd = str(validated_cwd)

        effective_timeout = timeout or self.max_timeout_seconds
        start_time = time.time()

        try:
            # Safe subprocess execution with fixed argument array (NO SHELL=TRUE)
            proc = subprocess.run(
                cmd_args,
                cwd=exec_cwd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                shell=False,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            stdout = proc.stdout[:self.max_output_bytes]
            stderr = proc.stderr[:self.max_output_bytes]
            if not redact:
                # Machine-readable output (JSON) is parsed first; callers redact each field they keep.
                return proc.returncode, stdout, redact_secrets(stderr), duration_ms
            return proc.returncode, redact_secrets(stdout), redact_secrets(stderr), duration_ms

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return -1, "", f"Execution exceeded maximum timeout of {effective_timeout}s.", duration_ms
        except FileNotFoundError:
            duration_ms = int((time.time() - start_time) * 1000)
            return 127, "", f"Executable '{cmd_args[0]}' is not installed or not in PATH.", duration_ms
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return -1, "", str(e), duration_ms
