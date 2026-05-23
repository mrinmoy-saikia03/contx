from pathlib import Path

from contx.bootstrap.ast_python import (
    BootstrapSymbol,
    parse_python_source,
)


def test_parse_top_level_function():
    src = '''"""module docstring"""


def hello(name):
    """Say hi."""
    return f"hi {name}"
'''
    result = parse_python_source(src)
    assert result.file_doc == "module docstring"
    syms = {s.symbol: s for s in result.symbols}
    assert "hello" in syms
    assert syms["hello"].doc == "Say hi."
    assert syms["hello"].kind == "function"


def test_parse_class_and_methods():
    src = '''
class Greeter:
    """A greeter."""

    def hello(self):
        """method doc"""
        pass

    def bye(self):
        pass
'''
    result = parse_python_source(src)
    syms = {s.symbol: s for s in result.symbols}
    assert "Greeter" in syms
    assert syms["Greeter"].doc == "A greeter."
    assert syms["Greeter"].kind == "class"
    assert "Greeter.hello" in syms
    assert syms["Greeter.hello"].doc == "method doc"
    assert syms["Greeter.hello"].kind == "method"
    assert "Greeter.bye" in syms
    assert syms["Greeter.bye"].doc is None


def test_parse_async_function():
    src = '''
async def fetch_user(user_id):
    """Async fetcher."""
    return user_id
'''
    result = parse_python_source(src)
    syms = {s.symbol: s for s in result.symbols}
    assert "fetch_user" in syms
    assert syms["fetch_user"].kind == "function"
    assert syms["fetch_user"].doc == "Async fetcher."


def test_parse_empty_module():
    result = parse_python_source("")
    assert result.file_doc is None
    assert result.symbols == []


def test_parse_no_docstrings():
    src = '''
def foo():
    return 1
'''
    result = parse_python_source(src)
    syms = {s.symbol: s for s in result.symbols}
    assert syms["foo"].doc is None


def test_parse_syntax_error_returns_empty():
    # We don't want bootstrap to crash on one bad file.
    result = parse_python_source("def def def")
    assert result.symbols == []


def test_bootstrap_symbol_is_immutable():
    s = BootstrapSymbol(symbol="foo", kind="function", doc=None)
    import dataclasses
    assert dataclasses.is_dataclass(s) and s.__dataclass_params__.frozen
