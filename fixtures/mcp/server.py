#!/usr/bin/env python3
"""Dependency-free stdio MCP server for the planned `mcp` scenario.

Exposes `bench_echo` plus N no-op tools (N from argv[1], default 0) so the arena can measure what a
harness spends per attached server and per declared tool. Newline-delimited JSON-RPC 2.0.
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from arena.payloads import echo_payload  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 0
TOOLS = [{'name': 'bench_echo', 'description': 'Return the benchmark echo payload.',
          'inputSchema': {'type': 'object', 'properties': {'size': {'type': 'integer'}, 'nonce': {'type': 'string'}}, 'required': ['size', 'nonce']}}]
TOOLS += [{'name': f'noop_{i}', 'description': f'No-op tool {i} used only to inflate the declared tool list.',
           'inputSchema': {'type': 'object', 'properties': {'value': {'type': 'string'}}}} for i in range(N)]


def reply(ident, result):
    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': ident, 'result': result}) + '\n')
    sys.stdout.flush()


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    method, ident, params = msg.get('method'), msg.get('id'), msg.get('params') or {}
    if method == 'initialize':
        reply(ident, {'protocolVersion': params.get('protocolVersion', '2025-06-18'), 'capabilities': {'tools': {}},
                      'serverInfo': {'name': 'arena-fixture', 'version': '1.0.0'}})
    elif method == 'tools/list':
        reply(ident, {'tools': TOOLS})
    elif method == 'tools/call':
        args = params.get('arguments') or {}
        text = echo_payload(int(args.get('size', 0)), str(args.get('nonce', ''))) if params.get('name') == 'bench_echo' else 'ok'
        reply(ident, {'content': [{'type': 'text', 'text': text}], 'isError': False})
    elif method == 'ping':
        reply(ident, {})
    elif ident is not None:
        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': f'unknown method {method}'}}) + '\n')
        sys.stdout.flush()
