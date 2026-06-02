"""Shared rate limiter (SlowAPI).

In-memory storage by default (fine for a single worker / small deploy). Point
`storage_uri` at Redis later for multi-worker setups.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
