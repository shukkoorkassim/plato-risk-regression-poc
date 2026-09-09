"""Regression tests for the CHECKOUT component (offline SwagLabs model).

These are the tests that catch the planted tax bug. On a fresh checkout of a
$29.99 backpack, tax should be 8% of the subtotal (2.40) and the total 32.39.
The buggy checkout_totals applies tax on an already-taxed base, so the numbers
come out wrong and test_tax_is_eight_percent_of_subtotal fails until the source
is fixed.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swaglabs import Cart, checkout_totals, complete_order
import pytest


def _one_backpack():
    c = Cart()
    c.add("sauce-labs-backpack")   # 29.99
    return c


def test_tax_is_eight_percent_of_subtotal():
    totals = checkout_totals(_one_backpack())
    # 29.99 * 0.08 = 2.3992 -> 2.40
    assert totals["tax"] == 2.40


def test_total_is_subtotal_plus_tax():
    totals = checkout_totals(_one_backpack())
    # 29.99 + 2.40 = 32.39
    assert totals["total"] == 32.39


def test_cannot_checkout_empty_cart():
    with pytest.raises(ValueError):
        complete_order(Cart())
