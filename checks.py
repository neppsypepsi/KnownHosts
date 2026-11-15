"""
checks.py: the core KnownHosts logic, as pure functions.

Nothing here touches MongoDB or the blockchain directly. The verdict function
receives the contacts list and a `get_rotated_to(address)` function as inputs,
so it can be unit-tested offline with fake data.

Security note: the server never holds private keys or funds. These functions
only *compare* public addresses.
"""
import re

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
ZERO_ADDRESS = "0x" + "0" * 40


def is_valid_address(value) -> bool:
    """True only for a string shaped like an EVM address (0x + 40 hex chars)."""
    return isinstance(value, str) and bool(ADDRESS_RE.match(value))


def normalize(address: str) -> str:
    """Lowercase for comparison. EVM addresses are case-insensitive; the mixed
    case form is only a checksum."""
    return address.strip().lower()


def is_lookalike(a: str, b: str) -> bool:
    """Same first 4 and last 4 hex chars, but a different address overall.
    This matches how wallets shorten addresses, e.g. 0xC644…C219, which is
    exactly what address-poisoning attackers imitate."""
    a, b = a.lower(), b.lower()
    return a != b and a[2:6] == b[2:6] and a[-4:] == b[-4:]


def diff(a: str, b: str) -> list:
    """Per-character comparison so the UI can color mismatches red.
    Case is ignored (checksum casing isn't a real difference)."""
    return [
        {"a": ca, "b": cb, "match": ca.lower() == cb.lower()}
        for ca, cb in zip(a, b)
    ]


def _contact_public(c: dict) -> dict:
    """The safe subset of a contact to return to the browser."""
    return {"id": str(c["_id"]), "name": c["name"], "address": c["address"]}


def _rotation_info(new_address, rotated_at, explorer_url):
    return {
        "new_address": new_address,
        "rotated_at": rotated_at,
        "explorer_url": explorer_url,
    }


def verdict(address, contacts, get_rotation, contact=None, explorer_url=None):
    """
    Decide what to tell the user about `address`.

    address       : the pasted address, already validated + normalized (lowercase)
    contacts      : list of contact dicts from Mongo ({_id, name, address, ...})
    get_rotation  : function(old_address) -> (rotated_to_lowercase_or_None, rotated_at)
                    (reads the on-chain registry)
    contact       : the contact the user says they are paying, or None for auto mode
    explorer_url  : link to the registry contract on the explorer

    Returns the response dict described in CLAUDE.md section 6.
    """
    result = {"address": address, "contact": None, "diff": None, "rotation": None}

    # Mode 1: the user picked "Paying: <contact>"
    if contact is not None:
        result["contact"] = _contact_public(contact)
        name = contact["name"]

        if address == contact["address"]:
            return {**result, "verdict": "trusted",
                    "message": f"Trusted contact: {name}."}

        new_addr, rotated_at = get_rotation(contact["address"])
        if new_addr and new_addr == address:
            return {**result, "verdict": "rotation_verified",
                    "rotation": _rotation_info(new_addr, rotated_at, explorer_url),
                    "message": f"Verified on Monad. {name} approved this address from their known wallet."}

        if is_lookalike(address, contact["address"]):
            result["diff"] = diff(contact["address"], address)
        return {**result, "verdict": "identity_changed",
                "message": f"This address was not approved by {name}'s known wallet."}

    # Mode 2: auto-detect against every contact
    for c in contacts:
        if address == c["address"]:
            return {**result, "verdict": "trusted", "contact": _contact_public(c),
                    "message": f"Trusted contact: {c['name']}."}

    for c in contacts:
        new_addr, rotated_at = get_rotation(c["address"])
        if new_addr and new_addr == address:
            return {**result, "verdict": "rotation_verified", "contact": _contact_public(c),
                    "rotation": _rotation_info(new_addr, rotated_at, explorer_url),
                    "message": f"Verified on Monad. {c['name']} approved this address from their known wallet."}

    for c in contacts:
        if is_lookalike(address, c["address"]):
            return {**result, "verdict": "lookalike", "contact": _contact_public(c),
                    "diff": diff(c["address"], address),
                    "message": f"This address imitates {c['name']}. Do not send."}

    return {**result, "verdict": "new",
            "message": "First time paying this address. Trust it?"}
