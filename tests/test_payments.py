"""Regression tests for the PAYMENTS component (offline SwagLabs model).

NEW this release. The promo-code feature (STORY-311) plus requirement REQ-411
("tax the discounted subtotal") mean the total must reflect the discount and tax
must be charged on the discounted base. With a 10% SAUCE10 code on a $29.99
backpack:
    discounted subtotal = 26.99
    tax                 = 26.99 * 0.08 = 2.16
    total               = 29.15
The buggy process_payment taxes the pre-discount subtotal (2.40) and over-charges
the customer, so test_promo_taxes_discounted_subtotal fails until the source is fixed.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swaglabs import Cart, apply_promo, process_payment


def _one_backpack():
    c = Cart()
    c.add("sauce-labs-backpack")   # 29.99
    return c


def test_apply_promo_discounts_subtotal():
    # 29.99 * 0.90 = 26.991 -> 26.99
    assert apply_promo(29.99, "SAUCE10") == 26.99


def test_unknown_promo_leaves_subtotal_unchanged():
    assert apply_promo(29.99, "NOPE") == 29.99


def test_promo_reduces_total():
    result = process_payment(_one_backpack(), promo="SAUCE10")
    assert result["discount"] == 3.00
    assert result["discounted_subtotal"] == 26.99


def test_promo_taxes_discounted_subtotal():
    result = process_payment(_one_backpack(), promo="SAUCE10")
    # tax must be on the discounted base: 26.99 * 0.08 = 2.1592 -> 2.16
    assert result["tax"] == 2.16
    # total = 26.99 + 2.16 = 29.15
    assert result["total"] == 29.15


def test_no_promo_matches_plain_checkout():
    result = process_payment(_one_backpack())
    # 29.99 + (29.99 * 0.08 = 2.40) = 32.39
    assert result["total"] == 32.39
