"""Regression tests for the INVENTORY component (offline SwagLabs model)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swaglabs import sort_inventory, INVENTORY


def test_catalog_has_six_items():
    assert len(INVENTORY) == 6


def test_sort_price_low_to_high():
    ordered = sort_inventory("lohi")
    prices = [INVENTORY[n] for n in ordered]
    assert prices == sorted(prices)


def test_sort_name_a_to_z():
    ordered = sort_inventory("az")
    assert ordered == sorted(ordered)
