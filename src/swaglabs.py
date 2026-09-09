"""
swaglabs.py -- a tiny offline model of https://www.saucedemo.com ("Swag Labs").

Why this exists: the real site needs a browser + network, which is flaky for a
live demo. This module reproduces saucedemo's *logic* (the same users, the same
catalog, the same cart + checkout math) so pytest can exercise it instantly with
zero setup. The Playwright tests in tests/test_live_saucedemo.py hit the real
site when you want that; these run anywhere.

COMPONENTS (these names match the defect CSVs, the release delta and the test map):
    login     - authentication, locked-out and problem users
    inventory - product catalog + sorting
    cart      - add / remove / count
    checkout  - totals, tax, order completion            <- Flow 1 high-risk area
    search    - product search / filtering
    payments  - promo codes + payment processing         <- Flow 2 changed area

TWO PLANTED BUGS (each flow finds and fixes its own):
    checkout.checkout_totals  - tax applied twice (Flow 1: defect-history driven)
    payments.process_payment  - promo discount ignored in the total, tax charged
                                on the pre-discount subtotal (Flow 2: change driven)
Run scripts/reset_demo.py to restore both bugs before a fresh demo.
"""

from dataclasses import dataclass, field

# ---- The real saucedemo users -------------------------------------------------
USERS = {
    "standard_user": "secret_sauce",
    "problem_user": "secret_sauce",
    "performance_glitch_user": "secret_sauce",
    "locked_out_user": "secret_sauce",   # valid password, but blocked
}
LOCKED_OUT = {"locked_out_user"}

TAX_RATE = 0.08  # saucedemo uses an 8% tax on the checkout overview


# ---- The real saucedemo inventory (name -> price) -----------------------------
INVENTORY = {
    "sauce-labs-backpack": 29.99,
    "sauce-labs-bike-light": 9.99,
    "sauce-labs-bolt-tshirt": 15.99,
    "sauce-labs-fleece-jacket": 49.99,
    "sauce-labs-onesie": 7.99,
    "test.allthethings()-tshirt-(red)": 15.99,
}


class LoginError(Exception):
    pass


def login(username: str, password: str) -> str:
    """Return a session token on success; raise LoginError otherwise."""
    if username in LOCKED_OUT:
        raise LoginError("Epic sadface: Sorry, this user has been locked out.")
    if username not in USERS or USERS[username] != password:
        raise LoginError("Epic sadface: Username and password do not match any user in this service.")
    return f"session-{username}"


def sort_inventory(order: str = "az") -> list:
    """Sort products the way the saucedemo dropdown does.

    az = name A->Z, za = name Z->A, lohi = price low->high, hilo = price high->low
    """
    items = list(INVENTORY.items())
    if order == "az":
        return [n for n, _ in sorted(items, key=lambda kv: kv[0])]
    if order == "za":
        return [n for n, _ in sorted(items, key=lambda kv: kv[0], reverse=True)]
    if order == "lohi":
        return [n for n, _ in sorted(items, key=lambda kv: kv[1])]
    if order == "hilo":
        return [n for n, _ in sorted(items, key=lambda kv: kv[1], reverse=True)]
    raise ValueError(f"unknown sort order: {order}")


def search_products(query: str) -> list:
    """Case-insensitive substring search over the product catalogue.

    Returns product keys whose name contains the query, sorted A->Z. An empty
    query returns nothing (saucedemo shows the full catalogue via sort, not search).
    """
    q = (query or "").strip().lower()
    if not q:
        return []
    return sorted(n for n in INVENTORY if q in n.lower())


@dataclass
class Cart:
    items: list = field(default_factory=list)

    def add(self, product: str) -> None:
        if product not in INVENTORY:
            raise KeyError(f"no such product: {product}")
        self.items.append(product)

    def remove(self, product: str) -> None:
        if product in self.items:
            self.items.remove(product)

    def count(self) -> int:
        """The number shown on the cart badge."""
        return len(self.items)

    def subtotal(self) -> float:
        return round(sum(INVENTORY[p] for p in self.items), 2)


def checkout_totals(cart: "Cart") -> dict:
    """Compute the checkout overview totals like saucedemo does.

    saucedemo shows: Item total (subtotal), Tax (8% of subtotal), Total.
    tax = subtotal * TAX_RATE, total = subtotal + tax.

    *** PLANTED BUG (Flow 1) ***
    The line below taxes an already-taxed base, so tax is charged twice and the
    total comes out high. The correct line is:
        tax = round(subtotal * TAX_RATE, 2)
    tests/test_checkout.py catches this; the Flow 1 agent reads this file, fixes
    the line, and re-runs until green.
    """
    subtotal = cart.subtotal()
    tax = round((subtotal + subtotal * TAX_RATE) * TAX_RATE, 2)  # BUG: tax applied twice
    total = round(subtotal + tax, 2)
    return {"subtotal": subtotal, "tax": tax, "total": total}


def complete_order(cart: "Cart") -> str:
    """Finish checkout. saucedemo shows 'Thank you for your order!'."""
    if cart.count() == 0:
        raise ValueError("cannot check out an empty cart")
    return "Thank you for your order!"


# ---- payments: NEW this release ----------------------------------------------
# Release delta (see data/release_delta/): a new promo-code feature (STORY-311),
# a requirement change to tax the *discounted* subtotal (REQ-both), and a bug
# fix (SWAG-231). That is why Flow 2 flags `payments` as the top area to re-test.
PROMO_CODES = {
    "SAUCE10": 0.10,   # 10% off the item subtotal
    "SAUCE25": 0.25,   # 25% off the item subtotal
}


def apply_promo(subtotal: float, code: str) -> float:
    """Return the item subtotal after applying a promo code.

    Unknown / empty codes leave the subtotal unchanged. Requirement REQ-411:
    the discount applies to the item subtotal, before tax.
    """
    rate = PROMO_CODES.get((code or "").strip().upper(), 0.0)
    return round(subtotal * (1 - rate), 2)


def process_payment(cart: "Cart", promo: str = "") -> dict:
    """Compute the final payment breakdown for the checkout overview.

    Requirement REQ-411 (this release): tax is charged on the DISCOUNTED
    subtotal, and the total reflects the discount.
        discounted = subtotal - promo discount
        tax        = discounted * TAX_RATE
        total      = discounted + tax

    *** PLANTED BUG (Flow 2) ***
    The line below taxes the pre-discount subtotal and adds tax to the discounted
    base, so the customer is over-charged whenever a promo is used. The correct
    line is:
        tax = round(discounted * TAX_RATE, 2)
    tests/test_payments.py catches this; the Flow 2 agent reads this file, fixes
    the line, and re-runs until green.
    """
    subtotal = cart.subtotal()
    discounted = apply_promo(subtotal, promo)
    tax = round(subtotal * TAX_RATE, 2)  # BUG: taxes pre-discount subtotal
    total = round(discounted + tax, 2)
    return {
        "subtotal": subtotal,
        "discount": round(subtotal - discounted, 2),
        "discounted_subtotal": discounted,
        "tax": tax,
        "total": total,
    }
