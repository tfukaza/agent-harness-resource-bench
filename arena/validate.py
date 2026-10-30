"""Integrity checks on captured traffic, independent of what the adapters claim.

Errors fail validation. Warnings (stray requests, truncated tool results where allowed, abandoned tool
calls) are reported but do not fail it: they are findings, not harness bugs the arena should hide.
"""
import json, pathlib, sys

from .payloads import ramp_expected_hashes


def last_stderr_line(directory: pathlib.Path) -> str:
    try:
        lines = [l.strip() for l in (directory / 'stderr.log').read_text(errors='replace').splitlines() if l.strip()]
        # Prefer the exception line over interpreter trailers such as "Node.js v24".
        for line in reversed(lines):
            if 'Error' in line or 'error' in line.split(':')[0].lower() or 'Exception' in line:
                return line[:300]
        return lines[-1][:300] if lines else 'no stderr'
    except OSError:
        return 'no stderr'


def validate(out: pathlib.Path):
    data = json.loads((out / 'results.json').read_text())
    errors, warnings = [], []
    for r in data['results']:
        tag = f"{r['scenario']} {r['harness']} {r['index']}"
        if r['status'] in ('unsupported',):
            continue
        s = r['scenario_config']
        if r['status'] in ('failed', 'timeout', 'memory_limit'):
            reason = last_stderr_line(out / r['scenario'] / f"{r['harness']}-{r['index']}")
            message = f"{tag}: trial ended with status {r['status']}: {reason}"
            # Some scenarios exist to see whether a harness survives (retry-storm, context-ramp): a
            # failure there is the measurement, not a broken arena.
            (warnings if s.get('failure_is_finding') else errors).append(message)
        requests = [q for q in r.get('requests', []) if q.get('kind') != 'stray']
        strays = [q for q in r.get('requests', []) if q.get('kind') == 'stray']
        if strays:
            hosts = sorted({q.get('detail', q.get('path', '?')) for q in strays})
            warnings.append(f'{tag}: {len(strays)} stray request(s): {hosts[:5]}')
        if r['status'] in ('success', 'concurrency_checkpoint', 'completed_with_compaction') and not requests and s['kind'] not in ('startup', 'idle'):
            errors.append(f'{tag}: no model requests captured')
        if s['kind'] in ('startup', 'idle'):
            if requests:
                warnings.append(f'{tag}: {len(requests)} model request(s) in a scenario that sends no turns')
            continue
        if s['kind'] == 'ramp':
            expected = ramp_expected_hashes(s['targets'], s['chunk'])
            for phase in r['phases']:
                if phase.get('phase') != 'checkpoint':
                    continue
                size = phase['bytes']
                if not any(q.get('user_bytes') == size and q.get('sha256') == expected[size] for q in requests):
                    # The runner already marks a trial whose checkpoint never reached the wire intact as
                    # completed_with_compaction; that is a measured behaviour, not a broken capture.
                    message = f'{tag}: history {size} not seen intact on the wire (compacted or dropped)'
                    (warnings if r['status'] == 'completed_with_compaction' else errors).append(message)
            continue
        # turns kind
        done_turns = max((p.get('n', 0) for p in r['phases'] if p.get('phase') == 'turn'), default=0)
        k = int(s.get('tool_calls_per_turn', 0))
        issued = r.get('issued_tool_calls', {})
        for t in range(1, done_turns + 1):
            if not any(q.get('user_turns') == t and q.get('kind') == 'text' for q in requests):
                errors.append(f'{tag}: turn {t} has no final text request')
            for idx in range(k):
                n = f't{t}-c{idx}'
                if n not in issued:
                    errors.append(f'{tag}: tool call {n} was never issued (harness declared no usable tool?)')
                    continue
                hits = [res for q in requests for res in q.get('tool_results', []) if res['nonce'] == n]
                if not hits:
                    errors.append(f'{tag}: tool result {n} never returned to the model')
                elif not any(h['complete'] for h in hits):
                    outcome = hits[-1].get('outcome', 'truncated')
                    (warnings if s.get('allow_truncation') else errors).append(f'{tag}: tool result {n} returned {outcome}')
        abandoned = [q for q in requests if q.get('kind') == 'tool_call_abandoned']
        if abandoned:
            errors.append(f'{tag}: {len(abandoned)} tool call(s) abandoned after repeated reissue')
        unavailable = [q for q in requests if q.get('kind') == 'tool_call_unavailable']
        if unavailable:
            errors.append(f'{tag}: harness declared no echo or shell tool in {len(unavailable)} request(s)')
    doc = {'passed': not errors, 'errors': errors, 'warnings': warnings}
    (out / 'validation.json').write_text(json.dumps(doc, indent=2))
    print(json.dumps(doc, indent=2))
    return doc


if __name__ == '__main__':
    root = pathlib.Path(__file__).resolve().parent.parent
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else sorted((root / 'results').iterdir())[-1]
    sys.exit(0 if validate(out)['passed'] else 1)
