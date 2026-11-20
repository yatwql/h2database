#!/usr/bin/env python3
"""The suite can only reach loopback: `_netguard` is installed and it bites."""

from __future__ import annotations

import socket
import unittest

import _netguard

TAGS = ('layer:infra', 'tier:fast')

# a public address the guard must refuse without ever dialling it
EXTERNAL_HOST = 'example.invalid'

class NetworkGuardTest(unittest.TestCase):
    def setUp(self):
        _netguard.install()

    def test_connecting_to_an_external_host_raises(self):
        with self.assertRaises(_netguard.BlockedNetwork):
            socket.create_connection((EXTERNAL_HOST, 80), timeout=0.01)

    def test_socket_connect_to_an_external_host_raises(self):
        sock = socket.socket()
        self.addCleanup(sock.close)
        with self.assertRaises(_netguard.BlockedNetwork):
            sock.connect((EXTERNAL_HOST, 80))

    def test_resolving_an_external_host_raises(self):
        with self.assertRaises(_netguard.BlockedNetwork):
            socket.getaddrinfo(EXTERNAL_HOST, 80)

    def test_loopback_is_still_allowed(self):
        self.assertTrue(_netguard._allowed('127.0.0.1'))
        self.assertTrue(_netguard._allowed('::1'))

if __name__ == '__main__':
    unittest.main()
