"""Scripted fake LLM server.

Speaks OpenAI Chat Completions, OpenAI Responses, Anthropic Messages (+count_tokens) and Gemini
generateContent, streamed or not. It never runs a model: for each request it inspects the
conversation the harness sent, decides whether the scripted scenario still owes a tool call for the
current user turn, and answers with either a tool call or deterministic text. Every request lands in
the ledger with sizes, hashes, timing and connection data. Unknown paths and proxied requests are
recorded as stray traffic and refused.
"""
import http.server, json, re, threading, time, uuid
from urllib.parse import unquote

from .payloads import ECHO_PREFIX, USER_PREFIX, echo_payload, nonce as make_nonce, sha256, tool_result_size

ECHO_TOOL = 'bench_echo'
MAX_REISSUE = 3
NONCE_RE = re.compile(r'ECHO-(t\d+-c\d+) ')


class RunState:
    def __init__(self, scenario, fixtures):
        self.scenario = scenario
        self.fixtures = fixtures
        self.issued = {}          # nonce -> {'turn','idx','size','time'}
        self.errors_served = {}   # turn -> count
        self.lock = threading.Lock()


class Ledger:
    def __init__(self):
        self.requests = []
        self.runs = {}
        self.lock = threading.Lock()
        self.connections = set()

    def register(self, run_id, scenario, fixtures):
        with self.lock:
            self.runs[run_id] = RunState(scenario, fixtures)

    def add(self, record):
        with self.lock:
            self.requests.append(record)

    def for_run(self, run_id):
        with self.lock:
            return [r for r in self.requests if r.get('run') == run_id]

    def issued(self, run_id):
        state = self.runs.get(run_id)
        return dict(state.issued) if state else {}

    def connection_is_new(self, key):
        with self.lock:
            new = key not in self.connections
            self.connections.add(key)
            return new


def walk_strings(value, out):
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, list):
        for item in value:
            walk_strings(item, out)
    elif isinstance(value, dict):
        for item in value.values():
            walk_strings(item, out)
    return out


def protocol_for(path):
    if 'count_tokens' in path:
        return 'anthropic_count'
    if 'chat/completions' in path:
        return 'chat'
    if path.rstrip('/').endswith('/responses') or '/responses' in path:
        return 'responses'
    if '/messages' in path:
        return 'anthropic'
    if 'generateContent' in path or 'streamGenerateContent' in path:
        return 'gemini'
    return None


def declared_tools(body, protocol):
    """Return [(name, json_schema)] for the tools the harness declared in this request."""
    tools = []
    for entry in body.get('tools') or []:
        if not isinstance(entry, dict):
            continue
        if protocol == 'chat':
            fn = entry.get('function') or {}
            if fn.get('name'):
                tools.append((fn['name'], fn.get('parameters') or {}))
        elif protocol == 'responses':
            if entry.get('type') == 'function' and entry.get('name'):
                tools.append((entry['name'], entry.get('parameters') or {}))
            elif entry.get('type') == 'local_shell':
                tools.append(('local_shell', {}))
        elif protocol == 'anthropic':
            if entry.get('name'):
                tools.append((entry['name'], entry.get('input_schema') or {}))
        elif protocol == 'gemini':
            for decl in entry.get('functionDeclarations') or entry.get('function_declarations') or []:
                if decl.get('name'):
                    tools.append((decl['name'], decl.get('parameters') or decl.get('parametersJsonSchema') or {}))
    return tools


def system_bytes(body, protocol):
    if protocol == 'chat':
        return sum(len(json.dumps(m.get('content', ''))) for m in body.get('messages', []) if isinstance(m, dict) and m.get('role') in ('system', 'developer'))
    if protocol == 'responses':
        return len(json.dumps(body.get('instructions', '')))
    if protocol in ('anthropic', 'anthropic_count'):
        return len(json.dumps(body.get('system', '')))
    if protocol == 'gemini':
        return len(json.dumps(body.get('systemInstruction') or body.get('system_instruction') or ''))
    return 0


def call_ids(nonce):
    compact = nonce.replace('-', '')
    return {f'toolu_{compact}', f'call_{compact}', f'fc_{compact}', f'lsh_{compact}'}


def choose_tool_call(tools, nonce, size, fixtures):
    """Pick the harness's echo mechanism and build arguments for it.

    Preference: a tool named bench_echo (possibly MCP-prefixed), else a built-in shell tool that
    `cat`s the pre-generated fixture file holding the identical payload.
    """
    names = dict(tools)
    for name in names:
        if name == ECHO_TOOL or name.endswith('__' + ECHO_TOOL):
            return name, {'size': size, 'nonce': nonce}, 'echo'
    path = f'{fixtures}/echo/{nonce}.txt'
    for name in ('Bash', 'shell', 'shell_command', 'exec_command'):
        if name in names:
            props = (names[name] or {}).get('properties') or {}
            key = 'command' if 'command' in props else 'cmd' if 'cmd' in props else 'command'
            typ = (props.get(key) or {}).get('type')
            value = ['cat', path] if typ == 'array' else f'cat {path}'
            return name, {key: value}, 'shell'
    if 'local_shell' in names:
        return 'local_shell', {'command': ['cat', path]}, 'shell'
    return None, None, None


class Handler(http.server.BaseHTTPRequestHandler):
    ledger: Ledger = None
    protocol_version = 'HTTP/1.1'
    server_version = 'arena-fake-llm/1.0'

    def log_message(self, *args):
        pass

    # ---- stray traffic -------------------------------------------------------------------
    def _stray(self, detail, status=404):
        rec = {'run': self._run_id(), 'path': self.path, 'method': self.command, 'protocol': None, 'stream': False,
               'time': time.time(), 'duration': 0.0, 'kind': 'stray', 'status': status, 'detail': detail,
               'request_bytes': int(self.headers.get('Content-Length') or 0), 'response_bytes': 0,
               'new_connection': self.ledger.connection_is_new(self.client_address)}
        length = int(self.headers.get('Content-Length') or 0)
        if length:
            self.rfile.read(length)
        self.ledger.add(rec)
        body = json.dumps({'error': 'arena: unexpected request', 'detail': detail}).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._stray('GET ' + self.path)

    def do_PUT(self):
        self._stray('PUT ' + self.path)

    def do_DELETE(self):
        self._stray('DELETE ' + self.path)

    def do_CONNECT(self):
        self._stray('CONNECT ' + self.path, status=403)
        self.close_connection = True

    def _run_id(self):
        parts = self.path.split('/')
        if len(parts) > 2 and parts[1] == 'run':
            return unquote(parts[2])
        return None

    # ---- model endpoints -----------------------------------------------------------------
    def do_POST(self):
        if self.path.startswith('http://') or self.path.startswith('https://'):
            return self._stray('proxied POST ' + self.path, status=403)
        protocol = protocol_for(self.path)
        run_id = self._run_id()
        state = self.ledger.runs.get(run_id) if run_id else None
        if protocol is None or state is None:
            return self._stray('POST ' + self.path)
        t0 = time.time()
        raw = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        try:
            body = json.loads(raw or b'{}')
        except ValueError:
            body = {}
        endpoint = self.path.split('?')[0].rsplit('/', 1)[-1]
        streaming = bool(body.get('stream')) or 'alt=sse' in self.path or endpoint.startswith('streamGenerateContent')
        strings = walk_strings(body, [])
        user = [s for s in strings if s.startswith(USER_PREFIX)]
        turn = len(user)
        retained = set(NONCE_RE.findall('\n'.join(s for s in strings if ECHO_PREFIX in s)))
        tools = declared_tools(body, protocol)
        record = {
            'run': run_id, 'path': self.path, 'method': 'POST', 'protocol': protocol, 'stream': streaming,
            'time': t0, 'request_bytes': len(raw), 'user_bytes': sum(len(s) for s in user),
            'sha256': [sha256(s) for s in user], 'user_turns': turn,
            'tool_names': [n for n, _ in tools], 'tool_schema_bytes': len(json.dumps(body.get('tools') or [])),
            'system_bytes': system_bytes(body, protocol), 'cache_control': b'cache_control' in raw,
            'retained_tool_results': len(retained), 'tool_results': [],
            'new_connection': self.ledger.connection_is_new(self.client_address),
            'model': body.get('model'),
        }
        scenario = state.scenario
        usage_tokens = max(1, (record['user_bytes'] + sum(len(s) for s in strings if s.startswith(ECHO_PREFIX))) // 4)

        if protocol == 'anthropic_count':
            record['kind'] = 'count_tokens'
            return self._finish(record, t0, 200, {'input_tokens': usage_tokens})

        # Which of the tool calls scripted for this turn have already been answered?
        k = int(scenario.get('tool_calls_per_turn', 0)) if turn else 0
        answered = 0
        with state.lock:
            for idx in range(k):
                n = make_nonce(turn, idx)
                if n not in state.issued:
                    break
                marker = f'{ECHO_PREFIX}{n} '
                hit = [s for s in strings if marker in s]
                # A harness may replace a large result with a pointer (e.g. spooled to disk); the
                # tool-call id it echoes back still proves the call was answered.
                ids = call_ids(n)
                if not hit and not any(s in ids for s in strings):
                    break
                complete = any(echo_payload(state.issued[n]['size'], n) in s for s in hit)
                record['tool_results'].append({'nonce': n, 'complete': complete, 'outcome': 'complete' if complete else 'truncated' if hit else 'replaced'})
                answered += 1
            # Error injection: {turn, status, count} served before the real answer for that turn.
            for err in scenario.get('errors') or []:
                if int(err.get('turn', 0)) == turn and state.errors_served.get(turn, 0) < int(err.get('count', 1)):
                    state.errors_served[turn] = state.errors_served.get(turn, 0) + 1
                    record['kind'] = 'error'
                    return self._finish(record, t0, int(err.get('status', 500)),
                                        {'error': {'type': 'arena_injected', 'message': 'scripted failure', 'code': int(err.get('status', 500))}},
                                        headers={'Retry-After': str(err.get('retry_after', 0))})
            step = None
            if answered < k:
                n = make_nonce(turn, answered)
                size = tool_result_size(scenario, turn)
                name, args, mechanism = choose_tool_call(tools, n, size, state.fixtures)
                prior = state.issued.get(n)
                if name is None:
                    record['kind'] = 'tool_call_unavailable'
                    record['detail'] = 'no echo or shell tool declared'
                elif prior and prior['count'] >= MAX_REISSUE:
                    # The harness keeps coming back without the payload; stop asking so the trial can end.
                    record['kind'] = 'tool_call_abandoned'
                    record['detail'] = f'{n} issued {prior["count"]} times without a matching result'
                else:
                    if prior is None:
                        prior = state.issued[n] = {'turn': turn, 'idx': answered, 'size': size, 'time': t0, 'tool': name, 'mechanism': mechanism, 'count': 0}
                    prior['count'] += 1
                    step = ('tool_call', name, args, n)
                    record['kind'] = 'tool_call'
                    record['tool_call'] = {'nonce': n, 'tool': name, 'mechanism': mechanism, 'size': size, 'attempt': prior['count']}
        if step is None and record.get('kind') not in ('tool_call_unavailable', 'tool_call_abandoned'):
            record['kind'] = 'text'
        pacing = scenario.get('stream') or {}
        pieces = int(pacing.get('pieces', 1))
        interval = float(pacing.get('interval_ms', 0)) / 1000
        text_pieces = ['OK'] if pieces <= 1 else ['tok '] * pieces
        encoder = getattr(self, '_' + protocol)
        result, events = encoder(body, usage_tokens, step, text_pieces)
        return self._finish(record, t0, 200, result, events if streaming else None, interval)

    # ---- transport -----------------------------------------------------------------------
    def _finish(self, record, t0, status, result, events=None, interval=0.0, headers=None):
        sent = 0
        try:
            self.send_response(status)
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            if events is None:
                body = json.dumps(result).encode()
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                sent = len(body)
            else:
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Transfer-Encoding', 'chunked')
                self.end_headers()
                for i, (name, event) in enumerate(events):
                    if interval and i:
                        time.sleep(interval)
                    frame = ((f'event: {name}\n') if name else '') + 'data: ' + (event if isinstance(event, str) else json.dumps(event)) + '\n\n'
                    data = frame.encode()
                    self.wfile.write(f'{len(data):x}\r\n'.encode() + data + b'\r\n')
                    self.wfile.flush()
                    sent += len(data)
                self.wfile.write(b'0\r\n\r\n')
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            record['client_disconnected'] = True
        record['status'] = status
        record['response_bytes'] = sent
        record['duration'] = time.time() - t0
        self.ledger.add(record)

    # ---- protocol encoders: return (json_result, [(event_name_or_None, payload)]) -----------
    def _chat(self, body, tokens, step, pieces):
        ident = 'chatcmpl-' + uuid.uuid4().hex
        usage = {'prompt_tokens': tokens, 'completion_tokens': 1, 'total_tokens': tokens + 1}
        base = {'id': ident, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': body.get('model', 'fake')}
        if step:
            _, name, args, n = step
            call = {'id': 'call_' + n.replace('-', ''), 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}
            result = {**base, 'object': 'chat.completion', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': None, 'tool_calls': [call]}, 'finish_reason': 'tool_calls'}], 'usage': usage}
            events = [
                (None, {**base, 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': None, 'tool_calls': [{'index': 0, 'id': call['id'], 'type': 'function', 'function': {'name': name, 'arguments': ''}}]}, 'finish_reason': None}]}),
                (None, {**base, 'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': 0, 'function': {'arguments': json.dumps(args)}}]}, 'finish_reason': None}]}),
                (None, {**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'tool_calls'}], 'usage': usage}),
                (None, '[DONE]'),
            ]
            return result, events
        text = ''.join(pieces)
        result = {**base, 'object': 'chat.completion', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}], 'usage': usage}
        events = [(None, {**base, 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': ''}, 'finish_reason': None}]})]
        events += [(None, {**base, 'choices': [{'index': 0, 'delta': {'content': p}, 'finish_reason': None}]}) for p in pieces]
        events += [(None, {**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}], 'usage': usage}), (None, '[DONE]')]
        return result, events

    def _responses(self, body, tokens, step, pieces):
        rid = 'resp_' + uuid.uuid4().hex
        usage = {'input_tokens': tokens, 'input_tokens_details': {'cached_tokens': 0}, 'output_tokens': 1, 'output_tokens_details': {'reasoning_tokens': 0}, 'total_tokens': tokens + 1}
        shell = {'id': rid, 'object': 'response', 'created_at': int(time.time()), 'model': body.get('model', 'fake'), 'status': 'completed', 'output': [], 'usage': usage}
        events = [('response.created', {'type': 'response.created', 'sequence_number': 0, 'response': {**shell, 'status': 'in_progress', 'usage': None}})]
        if step:
            _, name, args, n = step
            call_id = 'call_' + n.replace('-', '')
            if name == 'local_shell':
                item = {'id': 'lsh_' + n.replace('-', ''), 'type': 'local_shell_call', 'status': 'completed', 'call_id': call_id, 'action': {'type': 'exec', 'command': args['command'], 'timeout_ms': 10000}}
                events += [('response.output_item.added', {'type': 'response.output_item.added', 'sequence_number': 1, 'output_index': 0, 'item': {**item, 'status': 'in_progress'}})]
            else:
                item = {'id': 'fc_' + n.replace('-', ''), 'type': 'function_call', 'status': 'completed', 'call_id': call_id, 'name': name, 'arguments': json.dumps(args)}
                events += [
                    ('response.output_item.added', {'type': 'response.output_item.added', 'sequence_number': 1, 'output_index': 0, 'item': {**item, 'status': 'in_progress', 'arguments': ''}}),
                    ('response.function_call_arguments.delta', {'type': 'response.function_call_arguments.delta', 'sequence_number': 2, 'item_id': item['id'], 'output_index': 0, 'delta': item['arguments']}),
                    ('response.function_call_arguments.done', {'type': 'response.function_call_arguments.done', 'sequence_number': 3, 'item_id': item['id'], 'output_index': 0, 'arguments': item['arguments']}),
                ]
        else:
            text = ''.join(pieces)
            item = {'id': 'msg_' + uuid.uuid4().hex, 'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': [{'type': 'output_text', 'text': text, 'annotations': []}]}
            events += [('response.output_item.added', {'type': 'response.output_item.added', 'sequence_number': 1, 'output_index': 0, 'item': {**item, 'status': 'in_progress', 'content': []}}),
                       ('response.content_part.added', {'type': 'response.content_part.added', 'sequence_number': 2, 'item_id': item['id'], 'output_index': 0, 'content_index': 0, 'part': {'type': 'output_text', 'text': '', 'annotations': []}})]
            events += [('response.output_text.delta', {'type': 'response.output_text.delta', 'sequence_number': 3 + i, 'item_id': item['id'], 'output_index': 0, 'content_index': 0, 'delta': p}) for i, p in enumerate(pieces)]
            events += [('response.output_text.done', {'type': 'response.output_text.done', 'sequence_number': 900, 'item_id': item['id'], 'output_index': 0, 'content_index': 0, 'text': text}),
                       ('response.content_part.done', {'type': 'response.content_part.done', 'sequence_number': 901, 'item_id': item['id'], 'output_index': 0, 'content_index': 0, 'part': item['content'][0]})]
        result = {**shell, 'output': [item]}
        events += [('response.output_item.done', {'type': 'response.output_item.done', 'sequence_number': 998, 'output_index': 0, 'item': item}),
                   ('response.completed', {'type': 'response.completed', 'sequence_number': 999, 'response': result})]
        return result, events

    def _anthropic(self, body, tokens, step, pieces):
        ident = 'msg_' + uuid.uuid4().hex
        head = {'id': ident, 'type': 'message', 'role': 'assistant', 'model': body.get('model', 'fake'), 'stop_sequence': None}
        if step:
            _, name, args, n = step
            block = {'type': 'tool_use', 'id': 'toolu_' + n.replace('-', ''), 'name': name, 'input': args}
            result = {**head, 'content': [block], 'stop_reason': 'tool_use', 'usage': {'input_tokens': tokens, 'output_tokens': 1}}
            events = [
                ('message_start', {'type': 'message_start', 'message': {**head, 'content': [], 'stop_reason': None, 'usage': {'input_tokens': tokens, 'output_tokens': 0}}}),
                ('content_block_start', {'type': 'content_block_start', 'index': 0, 'content_block': {**block, 'input': {}}}),
                ('content_block_delta', {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'input_json_delta', 'partial_json': json.dumps(args)}}),
                ('content_block_stop', {'type': 'content_block_stop', 'index': 0}),
                ('message_delta', {'type': 'message_delta', 'delta': {'stop_reason': 'tool_use', 'stop_sequence': None}, 'usage': {'output_tokens': 1}}),
                ('message_stop', {'type': 'message_stop'}),
            ]
            return result, events
        text = ''.join(pieces)
        result = {**head, 'content': [{'type': 'text', 'text': text}], 'stop_reason': 'end_turn', 'usage': {'input_tokens': tokens, 'output_tokens': 1}}
        events = [('message_start', {'type': 'message_start', 'message': {**head, 'content': [], 'stop_reason': None, 'usage': {'input_tokens': tokens, 'output_tokens': 0}}}),
                  ('content_block_start', {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})]
        events += [('content_block_delta', {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': p}}) for p in pieces]
        events += [('content_block_stop', {'type': 'content_block_stop', 'index': 0}),
                   ('message_delta', {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': 1}}),
                   ('message_stop', {'type': 'message_stop'})]
        return result, events

    def _gemini(self, body, tokens, step, pieces):
        usage = {'promptTokenCount': tokens, 'candidatesTokenCount': 1, 'totalTokenCount': tokens + 1}
        if step:
            _, name, args, n = step
            parts = [{'functionCall': {'name': name, 'args': args}}]
            result = {'candidates': [{'content': {'role': 'model', 'parts': parts}, 'finishReason': 'STOP', 'index': 0}], 'usageMetadata': usage, 'modelVersion': body.get('model', 'fake')}
            return result, [(None, result)]
        text = ''.join(pieces)
        result = {'candidates': [{'content': {'role': 'model', 'parts': [{'text': text}]}, 'finishReason': 'STOP', 'index': 0}], 'usageMetadata': usage, 'modelVersion': body.get('model', 'fake')}
        events = [(None, {'candidates': [{'content': {'role': 'model', 'parts': [{'text': p}]}, 'index': 0}]}) for p in pieces[:-1]]
        events += [(None, {'candidates': [{'content': {'role': 'model', 'parts': [{'text': pieces[-1]}]}, 'finishReason': 'STOP', 'index': 0}], 'usageMetadata': usage})]
        return result, events


class Server:
    """Owns the HTTP server thread and the ledger."""

    def __init__(self):
        self.ledger = Ledger()
        handler = type('ArenaHandler', (Handler,), {'ledger': self.ledger})
        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.httpd.daemon_threads = True
        self.httpd.handle_error = lambda request, client_address: None  # clients hanging up is normal
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.httpd.server_port}'

    def register(self, run_id, scenario, fixtures):
        self.ledger.register(run_id, scenario, fixtures)

    def shutdown(self):
        self.httpd.shutdown()
