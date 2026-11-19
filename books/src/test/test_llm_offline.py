#!/usr/bin/env python3
"""LLM providers offline: key resolution, mock provider and the Messages API."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture
import _netguard

TAGS = ('layer:infra', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

class OfflineProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.llm = _fixture.load_module(self.root, '_llm')

    def provider_patch(self, provider: str):
        """Patch the provider table so every scenario uses a network provider."""
        config = self.llm.providers()
        config['providers'] = {provider: {
            'kind': 'openai-compatible',
            'base_url': f'https://{provider}.invalid/v1',
            'api_key_env': f'{provider.upper()}_API_KEY',
            'models': [f'{provider}-test'],
        }}
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

class AnthropicTransportTest(unittest.TestCase):
    """The Anthropic-compatible chain: no sockets, payload and auth verified."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.llm = _fixture.load_module(self.root, '_llm')
        key_path = os.path.join(self.root, 'data', 'config', 'llm_key.json')
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        with open(key_path, 'w', encoding='utf-8') as fh:
            json.dump({'providers': {
                'demo-anthropic': {'api_key': 'sk-test', 'model': 'demo-model',
                              'endpoint': 'https://api.example.invalid/anthropic/v1/messages'}
            }}, fh)
        config = self.llm.providers()
        config['providers'] = {'demo-anthropic': {
            'kind': 'anthropic',
            'base_url': 'https://api.example.invalid/anthropic',
            'credentials_ref': 'demo-anthropic',
            'api_key_env': 'DEMO_ANTHROPIC_API_KEY',
            'models': ['demo-model'],
        }}
        config['default_provider'] = 'demo-anthropic'
        for scenario in config.setdefault('routing', {}).setdefault('scenario', {}).values():
            if isinstance(scenario, dict):
                scenario['provider'] = 'demo-anthropic'
        patch = mock.patch.object(self.llm, 'providers', return_value=config)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop('DEMO_ANTHROPIC_API_KEY', None)

    def fake_connection(self, status: int = 200, body: bytes = b'{}'):
        calls = {}

        class Response:
            def read(self_):
                return body

        class Connection:
            def __init__(self_, host, port, timeout=None):
                calls['host'] = host

            def request(self_, method, path, body=None, headers=None):
                calls['method'] = method
                calls['path'] = path
                calls['headers'] = dict(headers or {})
                calls['payload'] = json.loads(body or b'{}')

            def getresponse(self_):
                return Response()

            def close(self_):
                return None

        return Connection, calls

    def test_messages_request_shape_and_headers(self):
        connection, calls = self.fake_connection(
            body=json.dumps({'content': [{'type': 'text', 'text': '回答'}]}).encode())
        with mock.patch.object(self.llm.http.client, 'HTTPSConnection', connection):
            text = self.llm.complete('你好')
        self.assertEqual(text, '回答')
        self.assertTrue(calls['path'].endswith('/v1/messages'))
        self.assertEqual(calls['headers']['x-api-key'], 'sk-test')
        self.assertIn('anthropic-version', calls['headers'])
        self.assertEqual(calls['payload']['model'], 'demo-model')
        self.assertEqual(calls['payload']['messages'][0]['content'], '你好')

    def test_missing_text_is_an_error(self):
        connection, _calls = self.fake_connection(body=b'{"content": []}')
        with mock.patch.object(self.llm.http.client, 'HTTPSConnection', connection), \
                self.assertRaises(self.llm.LLMError):
            self.llm.complete('hi')

    def test_missing_key_names_both_sources(self):
        os.remove(os.path.join(self.root, 'data', 'config', 'llm_key.json'))
        with self.assertRaises(self.llm.LLMError) as ctx:
            self.llm.complete('hi')
        message = str(ctx.exception)
        self.assertIn('all providers failed', message)
        self.assertIn('llm_key.json', message)

    def test_status_reports_configured_providers_without_secrets(self):
        status = self.llm.status()
        self.assertIn('demo-anthropic', status['keys_configured'])
        self.assertNotIn('sk-test', json.dumps(status, ensure_ascii=False))

if __name__ == '__main__':
    unittest.main()
