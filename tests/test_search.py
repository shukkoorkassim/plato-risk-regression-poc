"""Regression tests for the SEARCH component (offline SwagLabs model)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swaglabs import search_products


def test_search_matches_substring():
    results = search_products("fleece")
    assert results == ["sauce-labs-fleece-jacket"]


def test_search_is_case_insensitive():
    assert search_products("BACKPACK") == ["sauce-labs-backpack"]


def test_empty_query_returns_nothing():
    assert search_products("") == []


def test_search_returns_sorted_results():
    results = search_products("sauce-labs")
    assert results == sorted(results)
