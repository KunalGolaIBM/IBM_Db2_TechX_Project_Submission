"""
Unit tests for CodeFix AI Agent Service (agent_service.py)
Tests prompt engineering, LangChain integration, fallback behaviors,
and code extraction without requiring a live Ollama connection.
"""

from unittest.mock import patch, MagicMock
import pytest
from langchain_core.messages import AIMessage

import agent_service
from config import Config


def test_system_prompts_coverage():
    """Verify system instructions exist for all four required modes."""
    required_modes = ["write", "debug", "improve", "explain"]
    for mode in required_modes:
        assert mode in agent_service.SYSTEM_PROMPTS
        prompt = agent_service.SYSTEM_PROMPTS[mode]
        assert len(prompt) > 100
        # Check security rule is present in prompts
        assert "untrusted" in prompt.lower()


def test_extract_code_and_explanation_with_markdown_fencing():
    """Test extracting code from triple backtick markdown blocks."""
    raw_output = """
Here is the requested Python solution:

```python
def multiply(a, b):
    return a * b
```

### Solution Overview
This function multiplies two numbers together.
"""
    code, explanation = agent_service.extract_code_and_explanation(raw_output, default_language="python")
    assert "def multiply(a, b):" in code
    assert "return a * b" in code
    assert "Solution Overview" in explanation
    assert "```python" not in explanation


def test_extract_code_and_explanation_fallback():
    """Test fallback when model does not use markdown code blocks."""
    raw_code = "def simple_func():\n    return 42"
    code, explanation = agent_service.extract_code_and_explanation(raw_code, default_language="python")
    assert "def simple_func():" in code


def test_check_ollama_status_offline():
    """When Ollama is not running, check_ollama_status should return False and actionable advice."""
    with patch("requests.get", side_effect=Exception("Connection refused")):
        is_online, message, models = agent_service.check_ollama_status()
        assert is_online is False
        assert len(models) == 0
        assert "failed" in message.lower() or "connect" in message.lower()


def test_execute_task_offline_graceful_response():
    """When Ollama is offline, execute_task must return structured guidance without crashing."""
    with patch("agent_service.check_ollama_status", return_value=(False, "Ollama connection offline", [])):
        result = agent_service.execute_task(
            mode="write",
            language="python",
            prompt="Create a calculator"
        )
        assert result["mode"] == "write"
        assert result["language"] == "python"
        assert "Local AI Model Unavailable" in result["generated_code"]
        assert "ollama serve" in result["explanation"]
        assert "Offline" in result["model_name"]


def test_execute_task_with_mocked_model():
    """Test end-to-end task execution with a mocked LangChain ChatOllama response."""
    mock_aimessage = AIMessage(content="""
```python
def add(a, b):
    return a + b
```
### Explanation
Function performs addition.
""")
    mock_chat = MagicMock()
    mock_chat.invoke.return_value = mock_aimessage

    with patch("agent_service.check_ollama_status", return_value=(True, "Online", ["qwen2.5-coder:3b"])):
        with patch("agent_service.get_chat_model", return_value=mock_chat):
            result = agent_service.execute_task(
                mode="write",
                language="python",
                prompt="Write add function"
            )

            assert result["mode"] == "write"
            assert result["language"] == "python"
            assert "def add(a, b):" in result["generated_code"]
            assert "Explanation" in result["explanation"]
            assert result["model_name"] == Config.OLLAMA_MODEL


def test_process_followup_with_mocked_model():
    """Test conversational follow-up execution with mocked LangChain response."""
    mock_aimessage = AIMessage(content="""
```python
def add(a: int, b: int) -> int:
    \"\"\"Add two numbers with type hints.\"\"\"
    return a + b
```
Added type hints and docstring as requested.
""")
    mock_chat = MagicMock()
    mock_chat.invoke.return_value = mock_aimessage

    with patch("agent_service.check_ollama_status", return_value=(True, "Online", ["qwen2.5-coder:3b"])):
        with patch("agent_service.get_chat_model", return_value=mock_chat):
            result = agent_service.process_followup(
                message="Add type hints",
                current_code="def add(a, b): return a + b",
                language="python",
                history=[{"role": "user", "content": "Write add"}]
            )

            assert result["success"] is True
            assert "def add(a: int, b: int)" in result["generated_code"]
            assert "Added type hints" in result["reply"]

