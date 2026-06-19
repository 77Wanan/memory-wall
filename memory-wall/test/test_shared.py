"""Tests for shared utilities."""

import sys
import pathlib

# Add backend dir to path so we can import shared
_backend = str(pathlib.Path(__file__).resolve().parent.parent / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from shared import cosine_similarity


def test_cosine_similarity_identical():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert cosine_similarity(a, b) == 1.0


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert cosine_similarity(a, b) == 0.0


def test_cosine_similarity_zero_vector():
    a = [0.0, 0.0]
    b = [1.0, 0.0]
    assert cosine_similarity(a, b) == 0.0


def test_cosine_similarity_dimension_mismatch():
    """zip() truncates to shorter list, so [1,0]·[1] = 1*1 = 1, norm=1*1=1 → 1.0"""
    a = [1.0, 0.0]
    b = [1.0]
    assert cosine_similarity(a, b) == 1.0
