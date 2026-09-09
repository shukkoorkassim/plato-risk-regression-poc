"""Regression tests for the CART component (offline SwagLabs model)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swaglabs import Cart


def test_add_updates_badge_count():
    c = Cart()
    c.add("sauce-labs-backpack")
    c.add("sauce-labs-bike-light")
    assert c.count() == 2


def test_remove_updates_badge_count():
    c = Cart()
    c.add("sauce-labs-backpack")
    c.remove("sauce-labs-backpack")
    assert c.count() == 0


def test_subtotal_sums_prices():
    c = Cart()
    c.add("sauce-labs-backpack")     # 29.99
    c.add("sauce-labs-bike-light")   # 9.99
    assert c.subtotal() == 39.98
