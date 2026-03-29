"""
Rate limiting configuration (MAT-195).

Centralises the slowapi Limiter instance so both api_server.py and
route modules can import it without circular imports.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
