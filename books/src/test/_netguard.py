#!/usr/bin/env python3
"""Block every non-loopback network call for the whole test session.

The suite must be runnable offline and must never reach a real LLM provider or
any other external service: engines are either mocked or pointed at loopback.
``install()`` is idempotent and is called from ``_fixture`` on import.
"""
from __future__ import annotations

import socket

_LOOPBACK = {'127.0.0.1', '::1', 'localhost', '', None}
_installed = False


class BlockedNetwork(RuntimeError):
    """Raised when a test tries to open a connection to a non-local host."""


def _allowed(host) -> bool:
    return str(host) in _LOOPBACK


def install() -> None:
    """Patch socket so only loopback connections are possible."""
    global _installed
    if _installed:
        return

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    def connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if not _allowed(host):
            raise BlockedNetwork(f'test suite must not connect to {host}')
        return original_connect(self, address, *args, **kwargs)

    def connect_ex(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if not _allowed(host):
            raise BlockedNetwork(f'test suite must not connect to {host}')
        return original_connect_ex(self, address, *args, **kwargs)

    def create_connection(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if not _allowed(host):
            raise BlockedNetwork(f'test suite must not connect to {host}')
        return original_create(address, *args, **kwargs)

    def getaddrinfo(host, *args, **kwargs):
        if not _allowed(host):
            raise BlockedNetwork(f'test suite must not resolve {host}')
        return original_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.create_connection = create_connection
    socket.getaddrinfo = getaddrinfo
    _installed = True


def active() -> bool:
    return _installed
