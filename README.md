# KnownHosts

**A non-custodial transaction firewall that brings SSH's `known_hosts` model to crypto payments on Monad.**

🔗 **Live app:** https://knownhosts.vercel.app
📜 **Registry contract (Monad Testnet):** [`0xaE8F6e031C1181a7242D7719A91Fbd1D9aA90e32`](https://testnet.monadexplorer.com/address/0xaE8F6e031C1181a7242D7719A91Fbd1D9aA90e32) (source verified on Sourcify)
🎥 **Demo video:** _link added after recording_

Built solo at **Monad Blitz Oregon** (Nov 15, 2026).

---

## The problem

Crypto payments can't be undone, and two common scams exploit how people pick a recipient.

**1. Address poisoning.** Bots watch the chain. When you pay a friend, a bot generates an address that starts and ends with the same characters as your friend's, then sends you a worthless 0-value transaction from it. Wallets shorten addresses to `0xC644…C219`, so the fake sits in your history looking identical to your friend's. One day you copy the wrong one.

**2. "I got a new wallet."** A scammer messages you pretending to be a friend with a new address. The catch is that real people *do* change wallets, and today no wallet can tell a legitimate change from an impersonation. Both are just "a new address."

## The idea

SSH solved this for servers decades ago. Your computer remembers each server's fingerprint (`~/.ssh/known_hosts`). If it ever changes, you get a loud warning before anything happens:

```
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
```

KnownHosts does the same for payments:

- **Trust on first use:** contacts you've verified are saved as known hosts.
- **Lookalike detection:** an address that imitates a contact is blocked, with the differing characters highlighted.
- **Verified address changes on Monad:** when a contact really changes wallets, they approve the new address **from their old wallet** in a small registry contract. Only the old key can write that record, so KnownHosts can tell a real change from an impersonation.

## How it works

```
 Browser (wallet UI)            Flask server                    Monad Testnet
 ────────────────────          ──────────────────────          ─────────────────────────
 paste address  ── POST /api/check ──▶  compare to contacts      KnownHostsRegistry
                                        (MongoDB Atlas)          rotatedTo[old] = new
                                        read registry ◀── web3 ── (written only by old key)
 verdict panel  ◀───────────────────── verdict

 "Alice's wallet" page ── MetaMask signs rotate(newAddress) ──▶ registry   (server not involved)
```

### Verdicts

| Verdict | When | UI |
|---|---|---|
| 🟢 `trusted` | Address is exactly a saved contact | "Trusted contact: Alice" |
| ✅ `rotation_verified` | The contact's old wallet approved this address on-chain | "Verified on Monad" + explorer link + update contact |
| 🔴 `identity_changed` | You're paying a specific contact, and this address is neither theirs nor approved by them | SSH-style "RECIPIENT IDENTIFICATION HAS CHANGED" |
| 🔴 `lookalike` | Same first 4 and last 4 hex characters as a contact, different middle | Both full addresses with differences highlighted |
| 🟡 `new` | Never seen before | "First time paying this address. Trust it?" |

If the chain can't be reached, the API **fails closed** (HTTP 503, "do not send yet") instead of guessing.

### The contract

[`contracts/KnownHostsRegistry.sol`](contracts/KnownHostsRegistry.sol), about 30 lines:

```solidity
function rotate(address newAddress) external   // rotatedTo[msg.sender] = newAddress
function revoke() external                      // undo your own rotation
```

Entries are keyed by `msg.sender`, so **only the owner of the old wallet can approve a new one**. Not the KnownHosts server, and not an attacker.

## Demo

1. **Spot the fake.** Recent Activity has two rows that both read `0xc644…c219`. Check the 0-MON one → 🔴 lookalike, with the different middle highlighted.
2. **Fake "new wallet" text.** A text claiming to be Alice arrives with a new address. Paying: Alice → 🔴 *recipient identification has changed*.
3. **The real Alice's text.** Her real new address → still 🔴. A text message isn't proof.
4. **Alice proves it.** On "Alice's wallet", she signs `rotate(newAddress)` from her old wallet in MetaMask → confirmed on Monad.
5. **Check again.** Same address → ✅ verified on Monad.

Wallet history and text messages are simulated for the demo. Address-change verification is live on Monad Testnet.

## Security notes

- **Non-custodial.** The server never holds private keys or funds. It only reads public data; all signing happens in the user's MetaMask.
- **Unforgeable address changes.** Approvals live on-chain, keyed by `msg.sender`. The server can read them but can't create them.
- **Server-side re-verification.** "Update contact" re-reads the registry on the server, so the browser can't just claim a rotation happened.
- **Input validation.** Addresses must match `^0x[0-9a-fA-F]{40}$`, and IDs must parse as `ObjectId`. Only validated, typed values reach MongoDB queries, never raw request JSON (no NoSQL injection).
- **Fails closed.** RPC errors return "do not send yet", never a false 🟢.
- **Secrets** live in `.env` and Vercel environment variables, never in git. The poisoned flag on demo history rows is never sent to the browser.
- **Known limitation:** if a contact's *old* key is stolen, the thief could approve a new address. Roadmap: a 48-hour pending window during which the owner can `revoke()`, plus an optional guardian co-signer.

## Who pays

- **Wallets and payment apps:** an SDK/API to add pre-send checks; licensed per monthly active user.
- **DAO treasuries, payroll and accounts-payable tools:** a policy firewall so funds only go to known or verified recipients. Changing a vendor's payout address is a classic fraud vector in traditional finance too.
- **Exchanges and custodians:** verified withdrawal address books.

The registry itself stays an open public good; revenue comes from integrations and team features.

## Tech stack

Python · Flask · MongoDB Atlas (PyMongo) · web3.py · Solidity (Remix) · ethers.js v6 + MetaMask · Vercel

```
app.py         Flask routes (pages + JSON API); Vercel entrypoint
checks.py      pure functions: validation, is_lookalike, diff, verdict
chain.py       read-only web3.py access: balance, registry reads
db.py          MongoDB client (created once, reused)
seed.py        demo data: contacts, simulated history with poisoned rows
contracts/     KnownHostsRegistry.sol + abi.json
templates/     dashboard, contacts, Alice's wallet
static/        CSS + plain JS (no build step)
tests/         pytest for lookalike + verdict logic
```

## Run it locally

```bash
git clone https://github.com/neppsypepsi/KnownHosts.git && cd KnownHosts
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in MONGODB_URI, REGISTRY_ADDRESS, demo addresses
python seed.py              # create demo data (drops and recreates collections)
python app.py               # http://127.0.0.1:5001
python -m pytest -q         # unit tests
```

**Reset the demo:** call `revoke()` from Alice's old wallet on `/rotate`, then rerun `python seed.py`.

**Dashboard shortcuts (demo):** `Ctrl+J` scammer text · `Ctrl+K` Alice's text · `Ctrl+N` clear messages.

## API

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/check` | `{address, contact_id?}` → verdict |
| POST | `/api/contacts` | Add a contact (trust on first use) |
| POST | `/api/contacts/<id>/address` | Move a contact to their on-chain-verified new address |
| GET | `/api/config` | Chain ID, registry address, ABI |
| GET | `/api/activity` | Simulated wallet history |
| POST | `/api/demo/reset` | Reseed demo data (requires `X-Reset-Token`) |
