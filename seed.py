"""
seed.py: (re)create demo data. DROPS contacts, activity, and checks.

    python seed.py

Wallet history is simulated. The poisoned lookalike address is hand-made:
nobody owns it, so NEVER send MON to it.
"""
import os
import random
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from eth_account import Account

load_dotenv()

HEX = "0123456789abcdef"


def random_address() -> str:
    return Account.create().address.lower()


def lookalike_of(address: str) -> str:
    """Keep '0x' + first 4 hex chars and the last 4, randomize the middle.
    That's what a wallet shows (0xC644…C219), so the fake looks identical."""
    a = address.lower()
    middle = "".join(random.choice(HEX) for _ in range(len(a) - 10))
    return a[:6] + middle + a[-4:]


def build(now=None):
    alice = os.environ.get("ALICE_OLD", "").strip().lower()
    if not alice:
        sys.exit("ALICE_OLD is not set in .env. Add Alice (old)'s full address first.")

    now = now or datetime.now(timezone.utc)
    names = ["Bob (roommate)", "Mom", "Landlord", "Coinbase deposit",
             "Club treasury", "Jordan (lab partner)"]
    addr = {"Alice": alice, **{n: random_address() for n in names}}

    contacts = [
        {"name": n, "address": a, "note": "",
         "first_trusted_at": now - timedelta(days=random.randint(10, 60)),
         "previous_addresses": []}
        for n, a in addr.items()
    ]

    poison_alice = lookalike_of(alice)
    poison_coinbase = lookalike_of(addr["Coinbase deposit"])

    def row(direction, who, amount, ago, poisoned=False, counterparty=None):
        return {
            "direction": direction,
            "counterparty": counterparty or addr[who],
            "label": None if poisoned else who,
            "amount": amount,
            "timestamp": now - ago,
            "is_poisoned": poisoned,   # never shown to the user
        }

    h, d = timedelta(hours=1), timedelta(days=1)
    activity = [
        # The poisoned row lands right after the real Alice payment, as attackers do.
        row("received", None, 0.0, 0.3 * h, poisoned=True, counterparty=poison_alice),
        row("sent", "Alice", 2.0, 0.5 * h),
        row("received", "Coinbase deposit", 5.0, 5 * h),
        row("sent", "Landlord", 1.5, 1 * d),
        row("sent", "Bob (roommate)", 0.25, 1.5 * d),
        row("received", None, 0.0, 2 * d, poisoned=True, counterparty=poison_coinbase),
        row("sent", "Coinbase deposit", 3.0, 2.1 * d),
        row("received", "Mom", 1.0, 3 * d),
        row("sent", "Jordan (lab partner)", 0.4, 3.5 * d),
        row("sent", "Club treasury", 0.75, 4 * d),
        row("received", "Bob (roommate)", 0.3, 5 * d),
        row("sent", "Alice", 0.8, 6 * d),
        row("received", "Coinbase deposit", 2.0, 6.5 * d),
    ]
    return contacts, activity


def seed():
    from db import activity, checks, contacts  # imported here so build() works offline
    c, a = build()
    contacts.drop(); activity.drop(); checks.drop()
    contacts.insert_many(c)
    activity.insert_many(a)
    contacts.create_index("address", unique=True)
    print(f"Seeded {len(c)} contacts and {len(a)} activity rows.")


if __name__ == "__main__":
    seed()
