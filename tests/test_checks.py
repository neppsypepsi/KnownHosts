"""Unit tests for checks.py. Run with:  python -m pytest -q"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from checks import diff, is_lookalike, is_valid_address, verdict

ALICE = "0xc6440000000000000000000000000000000ec219"
FAKE = "0xc644ffffffffffffffffffffffffffffffffc219"   # same first/last 4
ALICE_NEW = "0xa957900000000000000000000000000000d12ad0"
ATTACKER = "0x5741200000000000000000000000000000040b9d"
RANDOM = "0x1234500000000000000000000000000000000001"

CONTACTS = [{"_id": "1", "name": "Alice", "address": ALICE}]


def no_rotation(_):
    return (None, 0)


def alice_rotated(old):
    return (ALICE_NEW, 1731700000) if old == ALICE else (None, 0)


def test_validation():
    assert is_valid_address(ALICE)
    assert not is_valid_address("0x123")
    assert not is_valid_address({"$ne": None})  # NoSQL-injection-shaped input
    assert not is_valid_address(None)


def test_lookalike():
    assert is_lookalike(ALICE, FAKE)
    assert not is_lookalike(ALICE, ALICE)
    assert not is_lookalike(ALICE, RANDOM)


def test_diff_marks_middle():
    d = diff(ALICE, FAKE)
    assert all(x["match"] for x in d[:6]) and all(x["match"] for x in d[-4:])
    assert not all(x["match"] for x in d)


def test_auto_mode_verdicts():
    assert verdict(ALICE, CONTACTS, no_rotation)["verdict"] == "trusted"
    assert verdict(FAKE, CONTACTS, no_rotation)["verdict"] == "lookalike"
    assert verdict(RANDOM, CONTACTS, no_rotation)["verdict"] == "new"
    assert verdict(ALICE_NEW, CONTACTS, alice_rotated)["verdict"] == "rotation_verified"


def test_paying_contact_verdicts():
    c = CONTACTS[0]
    assert verdict(ALICE, CONTACTS, no_rotation, contact=c)["verdict"] == "trusted"
    assert verdict(ATTACKER, CONTACTS, alice_rotated, contact=c)["verdict"] == "identity_changed"
    assert verdict(ALICE_NEW, CONTACTS, no_rotation, contact=c)["verdict"] == "identity_changed"
    assert verdict(ALICE_NEW, CONTACTS, alice_rotated, contact=c)["verdict"] == "rotation_verified"
    r = verdict(FAKE, CONTACTS, no_rotation, contact=c)
    assert r["verdict"] == "identity_changed" and r["diff"]
