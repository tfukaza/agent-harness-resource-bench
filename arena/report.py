"""Render results.json into REPORT.md and summary.json.

Conventions: table cells are medians [min–max] across trials; "settled" is the median of the last ten
samples inside a checkpoint pause; missing values print as — and are never zero; N/A marks a harness
that cannot run the scenario.
"""
import json, pathlib, statistics, sys

from .capabilities import HARNESSES, ORDER

MIB = 1024 ** 2


def median_last(samples, n=10):
    return statistics.median(samples[-n:]) if samples else None


def settled_rss(run, **match):
    rows = [s['rss'] / MIB for s in run['samples'] if s['phase'] == 'checkpoint' and all(s.get(k) == v for k, v in match.items())]
    return median_last(rows)


def phase_rss(run, phase):
    return median_last([s['rss'] / MIB for s in run['samples'] if s['phase'] == phase])


def fmt(values, digits=1):
    values = [v for v in values if v is not None]
    if not values:
        return '—'
    if len(values) == 1:
        return f'{values[0]:.{digits}f}'
    return f'{statistics.median(values):.{digits}f} [{min(values):.{digits}f}–{max(values):.{digits}f}]'


def model_requests(run):
    return [q for q in run.get('requests', []) if q.get('kind') not in ('stray',)]


def strays(run):
    return sum(1 for q in run.get('requests', []) if q.get('kind') == 'stray')


def new_connections(run):
    return sum(1 for q in model_requests(run) if q.get('new_connection'))


def tool_gaps_ms(run):
    """Time between the server finishing a tool-call response and the harness's next request."""
    reqs = sorted(model_requests(run), key=lambda q: q['time'])
    gaps = []
    for a, b in zip(reqs, reqs[1:]):
        if a.get('kind') == 'tool_call':
            gaps.append((b['time'] - (a['time'] + a.get('duration', 0))) * 1000)
    return statistics.median(gaps) if gaps else None


def tool_outcomes(runs):
    counts = {'complete': 0, 'truncated': 0, 'replaced': 0}
    seen = set()
    for r in runs:
        for q in model_requests(r):
            for res in q.get('tool_results', []):
                key = (r['index'], res['nonce'])
                if key in seen:
                    continue
                seen.add(key)
                counts[res.get('outcome', 'complete' if res.get('complete') else 'truncated')] += 1
    return f"{counts['complete']}/{counts['truncated']}/{counts['replaced']}"


def turns_done(run):
    return max((p.get('n', 0) for p in run['phases'] if p.get('phase') == 'turn'), default=0)


def idle_cpu(run):
    return run.get('cpu_by_phase', {}).get('initialized')


def row_startup(runs):
    return [fmt([r['timing'].get('t_initialized') for r in runs], 2), fmt([phase_rss(r, 'initialized') for r in runs]),
            fmt([r['peak_rss_mib'] for r in runs]), fmt([r['cpu_seconds_sampled'] for r in runs], 2),
            fmt([r['max_processes'] for r in runs], 0), fmt([r['max_threads'] for r in runs], 0), fmt([r['max_fds'] for r in runs], 0),
            fmt([r['files'] for r in runs], 0), fmt([strays(r) for r in runs], 0)]


def row_idle(runs):
    def drift(r):
        first = [s['rss'] / MIB for s in r['samples'] if s['phase'] == 'initialized'][:10]
        last = [s['rss'] / MIB for s in r['samples'] if s['phase'] == 'initialized'][-10:]
        return (statistics.median(last) - statistics.median(first)) if first and last else None
    return [fmt([phase_rss(r, 'initialized') for r in runs]), fmt([drift(r) for r in runs], 2), fmt([idle_cpu(r) for r in runs], 2),
            fmt([r['max_threads'] for r in runs], 0), fmt([len(model_requests(r)) for r in runs], 0), fmt([strays(r) for r in runs], 0)]


def row_ramp(runs, scenario):
    row = [fmt([phase_rss(r, 'initialized') for r in runs])]
    for target in scenario['targets']:
        reached = [r for r in runs if any(q.get('user_bytes') == target for q in model_requests(r))]
        row.append(fmt([settled_rss(r, history_bytes=target) for r in reached]))
    row += [fmt([r['peak_rss_mib'] for r in runs]), fmt([r['cpu_seconds_sampled'] for r in runs], 2), fmt([r['wall_seconds'] for r in runs]),
            fmt([len(model_requests(r)) / max(1, turns_done(r)) for r in runs], 2), f"{sum(r['status'] == 'success' for r in runs)}/{len(runs)}"]
    return row


def row_turns(runs, scenario, checkpoints):
    row = [fmt([phase_rss(r, 'initialized') for r in runs])]
    for cp in checkpoints:
        row.append(fmt([settled_rss(r, turn=cp) for r in runs]))
    turns = [max(1, turns_done(r)) for r in runs]
    row += [fmt([r['peak_rss_mib'] for r in runs]), fmt([r['cpu_seconds_sampled'] for r in runs], 2),
            fmt([r['cpu_seconds_sampled'] / t * 1000 for r, t in zip(runs, turns)], 0), fmt([r['wall_seconds'] for r in runs]),
            fmt([len(model_requests(r)) / t for r, t in zip(runs, turns)], 2),
            fmt([tool_gaps_ms(r) for r in runs], 0) if scenario.get('tool_calls_per_turn') else '—',
            tool_outcomes(runs) if scenario.get('tool_calls_per_turn') else '—',
            fmt([sum(q.get('request_bytes', 0) for q in model_requests(r)) / t / 1024 for r, t in zip(runs, turns)], 1),
            fmt([sum(1 for q in model_requests(r) if q.get('cache_control')) / max(1, len(model_requests(r))) * 100 for r in runs], 0),
            fmt([new_connections(r) for r in runs], 0), fmt([strays(r) for r in runs], 0),
            fmt([r['max_processes'] for r in runs], 0), fmt([r['retained_bytes'] / 1024 for r in runs], 1),
            f"{sum(r['status'] == 'success' for r in runs)}/{len(runs)}"]
    return row


def aggregate_peak(runs):
    begin = min(r['started'] for r in runs)
    end = max(r['started'] + r['wall_seconds'] for r in runs)
    peak = 0
    tick = begin
    while tick <= end:
        total = 0
        for r in runs:
            if r['started'] <= tick < r['started'] + r['wall_seconds'] and r['samples']:
                s = min(r['samples'], key=lambda s: abs(r['started'] + s['elapsed'] - tick))
                total += s['rss']
        peak = max(peak, total)
        tick += 0.05
    return peak / MIB


def render(out: pathlib.Path):
    data = json.loads((out / 'results.json').read_text())
    results = data['results']
    validation = json.loads((out / 'validation.json').read_text()) if (out / 'validation.json').exists() else None
    versions = data.get('versions', {})
    host = data.get('host_at_start')
    if host:
        host_line = (f"Host at start: {host['available_mib'] / 1024:.1f} GiB of {host['total_mib'] / 1024:.1f} GiB available, "
                     f"swap {host['swap_used_mib'] / 1024:.1f} of {host['swap_total_mib'] / 1024:.1f} GiB used"
                     + (f", load {host['loadavg_1m']:.1f}" if host.get('loadavg_1m') is not None else '') + '.')
        if host.get('preflight_warnings'):
            host_line += ' **Preflight warned: ' + '; '.join(host['preflight_warnings']) + '.**'
    else:
        host_line = 'Host state at start was not recorded for this run.'
    lines = ['# Agent harness resource benchmark', '',
             f"Run `{out.name}` on {data['machine']}; RAM {data['ram_bytes'] / 1024 ** 3:.1f} GiB; {data.get('cpu_count', '?')} logical CPUs.", '',
             host_line, '',
             'Local scripted fake LLM endpoints only: no inference, no API charges, no accuracy claims. Every harness performs the same '
             'scripted turns and tool calls; differences are harness overhead. Memory is summed RSS over the process tree, which can '
             'double-count shared pages. CPU is sampled at 20 Hz and can miss short-lived children. Disk counts files retained in the '
             'isolated HOME at exit. "Stray" requests are HTTP calls to anything other than the arena endpoint (telemetry, update checks).', '',
             'Versions: ' + ', '.join(f'{k} {v}' for k, v in sorted(versions.items())) + '.', '']
    summary = {}
    scenarios = list(dict.fromkeys(r['scenario'] for r in results))
    for name in scenarios:
        runs_all = [r for r in results if r['scenario'] == name]
        scenario = runs_all[0]['scenario_config']
        kind = scenario['kind']
        lines += [f'## {name}', '', scenario.get('description', ''), '']
        harness_rows = {}
        for harness in ORDER:
            runs = [r for r in runs_all if r['harness'] == harness and r['status'] != 'unsupported']
            if any(r['harness'] == harness and r['status'] == 'unsupported' for r in runs_all):
                harness_rows[harness] = None
            elif runs:
                harness_rows[harness] = runs
        if not harness_rows:
            continue
        checkpoints = sorted({p['turn'] for r in runs_all for p in r['phases'] if p.get('phase') == 'checkpoint' and 'turn' in p})
        if kind == 'startup':
            header = ['harness', 'ready s', 'initialized RSS MiB', 'peak MiB', 'CPU s', 'procs', 'threads', 'fds', 'files', 'stray req']
        elif kind == 'idle':
            header = ['harness', 'initialized RSS MiB', f"drift over {scenario['idle_seconds']} s MiB", 'idle CPU s', 'threads', 'model req', 'stray req']
        elif kind == 'ramp':
            header = ['harness', 'init MiB'] + [f'{t // 1024} KiB' if t < MIB else f'{t // MIB} MiB' for t in scenario['targets']] + ['peak MiB', 'CPU s', 'wall s', 'req/turn', 'full ramp']
        else:
            header = ['harness', 'init MiB'] + [f'turn {cp} MiB' for cp in checkpoints] + ['peak MiB', 'CPU s', 'CPU ms/turn', 'wall s', 'req/turn', 'tool gap ms', 'results ok/trunc/repl', 'req KiB/turn', 'cache ctl %', 'new conns', 'stray req', 'procs', 'retained KiB', 'ok']
        lines += ['| ' + ' | '.join(header) + ' |', '|---|' + '---:|' * (len(header) - 1)]
        for harness, runs in harness_rows.items():
            if runs is None:
                row = ['N/A'] * (len(header) - 1)
            elif kind == 'startup':
                row = row_startup(runs)
            elif kind == 'idle':
                row = row_idle(runs)
            elif kind == 'ramp':
                row = row_ramp(runs, scenario)
            else:
                row = row_turns(runs, scenario, checkpoints)
            lines.append('| ' + ' | '.join([harness] + row) + ' |')
            if runs:
                summary.setdefault(name, {})[harness] = {
                    'peak_rss_mib': statistics.median(r['peak_rss_mib'] for r in runs),
                    'cpu_seconds': statistics.median(r['cpu_seconds_sampled'] for r in runs),
                    'wall_seconds': statistics.median(r['wall_seconds'] for r in runs),
                    'initialized_rss_mib': statistics.median([v for v in (phase_rss(r, 'initialized') for r in runs) if v is not None] or [0]),
                    'requests': statistics.median(len(model_requests(r)) for r in runs),
                    'stray_requests': statistics.median(strays(r) for r in runs),
                    'retained_bytes': statistics.median(r['retained_bytes'] for r in runs),
                    'statuses': [r['status'] for r in runs]}
        lines.append('')
        if scenario.get('instances'):
            lines += [f"Aggregate over {scenario['instances']} simultaneous instances:", '', '| harness | sampled aggregate peak MiB | finished | retained files | retained KiB |', '|---|---:|---:|---:|---:|']
            for harness, runs in harness_rows.items():
                if not runs:
                    continue
                lines.append(f"| {harness} | {aggregate_peak(runs):.1f} | {sum(r['status'] in ('success', 'concurrency_checkpoint') for r in runs)}/{len(runs)} | {sum(r['files'] for r in runs)} | {sum(r['retained_bytes'] for r in runs) / 1024:.1f} |")
            lines.append('')
        if kind == 'turns' and scenario.get('tool_calls_per_turn'):
            lines += ['Tool mechanism per harness: ' + '; '.join(f"{h}: {HARNESSES[h]['tool_mechanism']}" for h in harness_rows if harness_rows[h]) + '.', '']
    lines += ['## Host pressure', '',
              'Host-wide free memory, swap and pageouts sampled during each trial. Low free memory or non-zero pageouts mean '
              'macOS was compressing or paging, and RSS medians for those trials are noisy.', '',
              '| scenario | harness | min host free MiB | max swap used MiB | pageouts |', '|---|---|---:|---:|---:|']
    for name in scenarios:
        for harness in ORDER:
            runs = [r for r in results if r['scenario'] == name and r['harness'] == harness and r['status'] != 'unsupported']
            if runs:
                lines.append(f"| {name} | {harness} | {fmt([r.get('host_min_available_mib') for r in runs], 0)} | "
                             f"{fmt([r.get('host_max_swap_used_mib') for r in runs], 0)} | {fmt([r.get('host_pageouts') for r in runs], 0)} |")
    lines += ['', '## Validation', '']
    if validation:
        lines.append(f"Passed: {validation['passed']}. Errors: {len(validation['errors'])}. Warnings: {len(validation['warnings'])}.")
        lines += [f'- error: {e}' for e in validation['errors'][:40]]
        lines += [f'- warning: {w}' for w in validation['warnings'][:40]]
    else:
        lines.append('validation.json not found; run `bench.py validate`.')
    lines += ['', '## Limitations', '',
              '- Fake usage is synthetic (one token per four user bytes). Cost fields emitted by coding SDKs are estimates, not charges.',
              '- Harnesses that ignore HTTP(S)_PROXY can still reach the real network unseen; stray counts are a lower bound.',
              '- Write-byte counters are unavailable on macOS; retained bytes and sampled peak directory size stand in for write amplification.',
              '- RSS on macOS excludes pages the kernel has compressed; an idle process can read far below its true footprint and grow again when it wakes. Compare medians across trials and prefer Linux cgroup figures for ground truth.',
              '- "results ok/trunc/repl" counts tool results that reached the model complete, truncated, or replaced by a pointer (for example spooled to a file).',
              '- Runtime-only samples precede SDK imports. Native child runtimes often start on the first request, so the initialized column understates coding-harness cost; peak and in-turn samples include children.',
              '- Codex launches one `codex exec` per turn; Claude runs one streaming-input CLI session per trial. Both are the SDKs\' documented multi-turn paths, not tuned deployments.',
              '- Host pressure is sampled alongside each trial (see "Host pressure"). Trials whose minimum host free memory dropped low or whose pageouts are non-zero ran on a loaded machine; treat their RSS as noisy and prefer a rerun on a quiet host.',
              '', '## Trial status', '']
    for r in results:
        if r['status'] == 'unsupported':
            lines.append(f"- {r['scenario']} {r['harness']}: unsupported")
        else:
            host_free = r.get('host_min_available_mib')
            lines.append(f"- {r['scenario']} {r['harness']} {r['index']}: {r['status']}; peak {r['peak_rss_mib']:.1f} MiB; cpu {r['cpu_seconds_sampled']:.2f} s; requests {len(model_requests(r))}; stray {strays(r)}; retained {r['retained_bytes']} bytes"
                         + (f"; host free min {host_free:.0f} MiB." if host_free is not None else '.'))
    text = '\n'.join(lines) + '\n'
    (out / 'REPORT.md').write_text(text)
    (out / 'summary.json').write_text(json.dumps(summary, indent=1))
    return text


if __name__ == '__main__':
    root = pathlib.Path(__file__).resolve().parent.parent
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else sorted((root / 'results').iterdir())[-1]
    print(render(out))
