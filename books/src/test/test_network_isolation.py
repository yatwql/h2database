#!/usr/bin/env python3
"""The socket guard: non-loopback destinations are refused during tests."""

from __future__ import annotations

import os
import socket
import sys
import unittest

import _netguard

TAGS = ('layer:infra', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

class NetworkGuardTest(unittest.TestCase):
    def test_guard_is_installed(self):
        self.assertTrue(_netguard.active())

    def test_external_connect_is_blocked(self):
        with self.assertRaises(_netguard.BlockedNetwork):
            socket.create_connection(('example.com', 443), timeout=1)

    def test_external_dns_lookup_is_blocked(self):
        with self.assertRaises(_netguard.BlockedNetwork):
            socket.getaddrinfo('api.openai.com', 443)

    def test_loopback_is_allowed(self):
        server = socket.socket()
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        self.addCleanup(server.close)
        client = socket.create_connection(server.getsockname(), timeout=2)
        client.close()

if __name__ == '__main__':
    unittest.main()
