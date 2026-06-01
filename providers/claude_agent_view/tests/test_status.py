"""Tests for the terminal status authority."""
from providers.claude_agent_view.status import is_terminal, is_error, TERMINAL_STATUSES, ERROR_STATUSES
import pytest

def test_idle_is_terminal():
    assert is_terminal("idle")

def test_stopped_is_terminal():
    assert is_terminal("stopped")

def test_exited_is_terminal():
    assert is_terminal("exited")

def test_running_is_not_terminal():
    assert not is_terminal("running")

def test_busy_is_not_terminal():
    assert not is_terminal("busy")

def test_error_is_not_terminal():
    assert not is_terminal("error")

def test_error_is_error():
    assert is_error("error")

def test_idle_is_not_error():
    assert not is_error("idle")

def test_terminal_and_error_are_disjoint():
    assert TERMINAL_STATUSES.isdisjoint(ERROR_STATUSES)
