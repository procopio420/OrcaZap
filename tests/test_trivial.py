"""Trivial test to ensure CI works."""

import pytest


def test_trivial() -> None:
    """Trivial test that always passes."""
    assert True


def test_math() -> None:
    """Another trivial test."""
    assert 1 + 1 == 2


