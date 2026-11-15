"""
chain.py: read-only access to Monad Testnet via web3.py.

The server only READS the chain: balances and the registry's rotatedTo/rotatedAt.
It never signs anything and holds no private keys. All writes (rotate/revoke)
happen in the user's MetaMask on the /rotate page.
"""
import json
import os

from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

RPC_URL = os.environ.get("MONAD_RPC_URL", "https://testnet-rpc.monad.xyz")
REGISTRY_ADDRESS = os.environ.get("REGISTRY_ADDRESS", "")
EXPLORER = "https://testnet.monadexplorer.com"
CHAIN_ID = 10143

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 8}))

_ABI_PATH = os.path.join(os.path.dirname(__file__), "contracts", "abi.json")
try:
    with open(_ABI_PATH) as f:
        ABI = json.load(f)
except FileNotFoundError:
    ABI = []  # contract not deployed yet

registry = (
    w3.eth.contract(address=Web3.to_checksum_address(REGISTRY_ADDRESS), abi=ABI)
    if REGISTRY_ADDRESS and ABI else None
)


def get_balance(address: str):
    """MON balance as a float, or None if the RPC fails (the UI shows a dash)."""
    try:
        wei = w3.eth.get_balance(Web3.to_checksum_address(address))
        return float(Web3.from_wei(wei, "ether"))
    except Exception:
        return None


def get_rotation(old_address: str):
    """Return (new_address_lowercase or None, rotated_at_unix) from the registry."""
    if registry is None:
        return (None, 0)
    old = Web3.to_checksum_address(old_address)
    new = registry.functions.rotatedTo(old).call()
    if int(new, 16) == 0:
        return (None, 0)
    return (new.lower(), registry.functions.rotatedAt(old).call())


def registry_explorer_url():
    return f"{EXPLORER}/address/{REGISTRY_ADDRESS}" if REGISTRY_ADDRESS else None
