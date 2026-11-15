"""
db.py: one MongoDB client, created once at import and reused.

On Vercel (serverless) each warm instance reuses this module, so we don't open
a new connection per request.
"""
import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=8000)
db = client["knownhosts"]

contacts = db["contacts"]   # trusted address book
activity = db["activity"]   # simulated wallet history for the dashboard
checks = db["checks"]       # audit log of every address check
