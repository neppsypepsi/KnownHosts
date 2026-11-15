"""
app.py: KnownHosts Flask app (also the Vercel entrypoint: it exposes `app`).

KnownHosts is NON-CUSTODIAL: the server never holds private keys or funds.
It only reads public data (Mongo contacts, the on-chain registry) and returns
a verdict. All signing happens in the user's MetaMask.

Injection safety: request JSON is never passed into Mongo queries. We pull out
individual fields, validate them (regex / ObjectId), and only query with those.
"""
import json
import os
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

import chain
import checks as ck
from db import activity, checks, contacts

load_dotenv()
app = Flask(__name__)

YOU_ADDRESS = os.environ.get("YOU_ADDRESS", "").lower()
ALICE_NEW = os.environ.get("ALICE_NEW", "")


# ---------- helpers ----------

def short(addr: str) -> str:
    """Wallet-style shortening: 0xc644…c219"""
    return f"{addr[:6]}…{addr[-4:]}" if addr else ""


def bad(msg, code=400):
    return jsonify({"error": msg}), code


def find_contact(contact_id):
    """Look up a contact by id string; None if missing or not a valid ObjectId."""
    if not isinstance(contact_id, str):
        return None
    try:
        return contacts.find_one({"_id": ObjectId(contact_id)})
    except InvalidId:
        return None


def contact_json(c):
    return {
        "id": str(c["_id"]),
        "name": c["name"],
        "address": c["address"],
        "note": c.get("note", ""),
        "first_trusted_at": c["first_trusted_at"].isoformat() if c.get("first_trusted_at") else None,
        "previous_addresses": [
            {**p, "replaced_at": p["replaced_at"].isoformat()} for p in c.get("previous_addresses", [])
        ],
    }


def _aware(dt):
    """PyMongo returns naive UTC datetimes; mark them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def ago(dt) -> str:
    """Relative time like a wallet: '18m ago', '5h ago', '3d ago'."""
    secs = (datetime.now(timezone.utc) - _aware(dt)).total_seconds()
    if secs < 3600:
        return f"{max(1, int(secs // 60))}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def nice_date(dt) -> str:
    return _aware(dt).strftime("%b %-d, %Y")


app.jinja_env.filters["short"] = short
app.jinja_env.filters["ago"] = ago
app.jinja_env.filters["nice_date"] = nice_date


# ---------- pages ----------

@app.get("/")
def dashboard():
    rows = list(activity.find({}, {"is_poisoned": 0}).sort("timestamp", -1))  # never send is_poisoned
    return render_template(
        "dashboard.html",
        you=YOU_ADDRESS,
        balance=chain.get_balance(YOU_ADDRESS) if YOU_ADDRESS else None,
        rows=rows,
        contacts=list(contacts.find().sort("name", 1)),
        # Addresses for the simulated text messages (Ctrl+J / Ctrl+K on the dashboard)
        demo_msgs={"attacker": os.environ.get("ATTACKER", ""), "alice_new": ALICE_NEW},
    )


@app.get("/contacts")
def contacts_page():
    return render_template("contacts.html", contacts=list(contacts.find().sort("name", 1)))


@app.get("/rotate")
def rotate_page():
    return render_template("rotate.html")


# ---------- API ----------

@app.get("/api/config")
def api_config():
    return jsonify({
        "chainId": chain.CHAIN_ID,
        "registryAddress": chain.REGISTRY_ADDRESS,
        "abi": chain.ABI,
        "aliceNew": ALICE_NEW,
        "aliceOld": os.environ.get("ALICE_OLD", ""),
        "explorer": chain.EXPLORER,
    })


@app.get("/api/activity")
def api_activity():
    rows = activity.find({}, {"is_poisoned": 0}).sort("timestamp", -1)
    return jsonify([{**r, "_id": str(r["_id"]), "timestamp": r["timestamp"].isoformat()} for r in rows])


@app.post("/api/check")
def api_check():
    body = request.get_json(silent=True) or {}
    raw = body.get("address")
    if not ck.is_valid_address(raw):
        return bad("Not a valid address (expected 0x + 40 hex characters).")
    address = ck.normalize(raw)

    contact = None
    contact_id = body.get("contact_id")
    if contact_id:  # "" or missing => auto-detect
        contact = find_contact(contact_id)
        if contact is None:
            return bad("Unknown contact.", 404)

    try:
        result = ck.verdict(
            address,
            list(contacts.find()),
            chain.get_rotation,
            contact=contact,
            explorer_url=chain.registry_explorer_url(),
        )
    except Exception:
        # RPC failure etc. Fail closed: never call something "safe" when we couldn't check.
        return bad("Could not reach Monad Testnet to verify. Do not send yet.", 503)

    # Add "first trusted" date for the trusted message
    if result["verdict"] == "trusted" and result["contact"]:
        c = find_contact(result["contact"]["id"])
        if c and c.get("first_trusted_at"):
            result["contact"]["first_trusted_at"] = c["first_trusted_at"].isoformat()

    checks.insert_one({
        "input_address": address,
        "contact_id": contact["_id"] if contact else None,
        "verdict": result["verdict"],
        "created_at": datetime.now(timezone.utc),
    })
    return jsonify(result)


@app.post("/api/contacts")
def api_add_contact():
    """Trust on first use: save a new address under a name."""
    body = request.get_json(silent=True) or {}
    raw, name = body.get("address"), body.get("name")
    if not ck.is_valid_address(raw):
        return bad("Not a valid address.")
    if not isinstance(name, str) or not name.strip() or len(name) > 60:
        return bad("Name is required (max 60 characters).")
    address = ck.normalize(raw)
    if contacts.find_one({"address": address}):
        return bad("That address is already a contact.", 409)
    note = body.get("note") if isinstance(body.get("note"), str) else ""
    doc = {
        "name": name.strip(),
        "address": address,
        "note": note[:200],
        "first_trusted_at": datetime.now(timezone.utc),
        "previous_addresses": [],
    }
    contacts.insert_one(doc)
    return jsonify(contact_json(doc)), 201


@app.post("/api/contacts/<contact_id>/address")
def api_replace_address(contact_id):
    """After a rotation_verified check, move the contact to the new address.
    We re-check the registry here, so the browser can't just claim a rotation."""
    c = find_contact(contact_id)
    if c is None:
        return bad("Unknown contact.", 404)
    try:
        new_addr, _ = chain.get_rotation(c["address"])
    except Exception:
        return bad("Could not reach Monad Testnet to verify.", 503)
    if not new_addr:
        return bad("No on-chain approval found for this contact.", 409)
    contacts.update_one(
        {"_id": c["_id"]},
        {"$set": {"address": new_addr},
         "$push": {"previous_addresses": {
             "address": c["address"],
             "replaced_at": datetime.now(timezone.utc),
             "reason": "rotation verified on Monad",
         }}},
    )
    return jsonify(contact_json(contacts.find_one({"_id": c["_id"]})))


@app.post("/api/demo/reset")
def api_reset():
    token = os.environ.get("RESET_TOKEN")
    if not token or request.headers.get("X-Reset-Token") != token:
        return bad("Forbidden.", 403)
    import seed
    seed.seed()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5001)  # 5000 is often taken by macOS AirPlay
