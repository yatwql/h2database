#!/usr/bin/env python3
"""The suite must never touch the network: prove it, and prove the guard."""
from __future__ import annotations

import os
import socket
import sys
import tempfile
import unittest
from unittest import mock

import _fixture
import _netguard

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class GuardCase(unittest.TestCase):
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


class LLMOfflineCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.llm = _fixture.load_module(self.root, '_llm')

    def provider_patch(self, provider: str):
        """Patch the provider table so every scenario uses a network provider."""
        config = self.llm.providers()
        config.setdefault('providers', {})[provider] = {
            'kind': 'openai-compatible',
            'base_url': f'https://{provider}.invalid/v1',
            'api_key_env': f'{provider.upper()}_API_KEY',
            'models': [f'{provider}-test'],
        }
        config['default_provider'] = provider
        routing = config.setdefault('routing', {}).setdefault('scenario', {})
        for name, value in list(routing.items()):
            if isinstance(value, dict):
                value['provider'] = provider
            else:
                routing[name] = {'provider': provider}
        return mock.patch.object(self.llm, 'providers', return_value=config)

    def test_real_provider_without_key_is_refused(self):
        patch = self.provider_patch('openai')
        patch.start()
        self.addCleanup(patch.stop)
        with self.assertRaises(self.llm.LLMError):
            self.llm.complete('hi')

    def test_real_provider_never_reaches_the_network(self):
        patch = self.provider_patch('openai')
        patch.start()
        self.addCleanup(patch.stop)
        os.environ['OPENAI_API_KEY'] = 'test-key-not-real'
        self.addCleanup(os.environ.pop, 'OPENAI_API_KEY', None)
        with self.assertRaises(_netguard.BlockedNetwork):
            self.llm.complete('hi')

    def test_transport_is_mocked_and_parsed(self):
        patch = self.provider_patch('openai')
        patch.start()
        self.addCleanup(patch.stop)
        os.environ['OPENAI_API_KEY'] = 'test-key-not-real'
        self.addCleanup(os.environ.pop, 'OPENAI_API_KEY', None)
        reply = {'choices': [{'message': {'content': '离线回答'}}]}
        with mock.patch.object(self.llm, '_post_json', return_value=reply) as sender:
            text = self.llm.complete('hi')
        self.assertEqual(text, '离线回答')
        self.assertEqual(sender.call_count, 1)

    def test_key_file_is_used_when_env_is_absent(self):
        patch = self.provider_patch('deepseek')
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop('DEEPSEEK_API_KEY', None)
        key_path = os.path.join(self.root, 'data', 'config', 'llm_key.json')
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        with open(key_path, 'w', encoding='utf-8') as fh:
            fh.write('{"keys": {"deepseek": "sk-from-file"}}')
        self.assertEqual(self.llm._api_key('deepseek', {'api_key_env': 'DEEPSEEK_API_KEY'}),
                         'sk-from-file')

    def test_environment_wins_over_the_key_file(self):
        key_path = os.path.join(self.root, 'data', 'config', 'llm_key.json')
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        with open(key_path, 'w', encoding='utf-8') as fh:
            fh.write('{"keys": {"deepseek": "sk-from-file"}}')
        os.environ['DEEPSEEK_API_KEY'] = 'sk-from-env'
        self.addCleanup(os.environ.pop, 'DEEPSEEK_API_KEY', None)
        self.assertEqual(self.llm._api_key('deepseek', {'api_key_env': 'DEEPSEEK_API_KEY'}),
                         'sk-from-env')

    def test_mock_provider_never_opens_a_socket(self):
        with mock.patch('socket.socket.connect', side_effect=AssertionError('socket opened')):
            self.assertTrue(self.llm.complete('hi'))


if __name__ == '__main__':
    unittest.main()
