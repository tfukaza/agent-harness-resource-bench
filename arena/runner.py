"""Spawns harness adapters per scenario, samples them, and writes results.json."""
import concurrent.futures, json, os, pathlib, platform, signal, subprocess, threading, time
import psutil, yaml

from .capabilities import HARNESSES, ORDER, supports
from .payloads import echo_payload, nonce as make_nonce, tool_result_size
from .sampler import Sampler
from .server import Server

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / 'scenarios'
PYTHON = ROOT / '.venv' / 'bin' / 'python'
MEMORY_LIMIT = 4 * 1024 ** 3
STRIP_KEYS = ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'GOOGLE_API_KEY', 'GEMINI_API_KEY',
              'OPENAI_BASE_URL', 'ANTHROPIC_BASE_URL', 'LANGSMITH_API_KEY', 'LANGCHAIN_API_KEY']
DEFAULTS = {'kind': 'turns', 'turns': 10, 'prompt_bytes': 256, 'tool_calls_per_turn': 0, 'tool_result_bytes': 4096,
            'checkpoint_every': 0, 'pause_seconds': 2, 'timeout_seconds': 300, 'instances': 0, 'requires': [],
            'targets': [4096, 262144, 1048576, 4194304], 'chunk': 262144, 'idle_seconds': 60}


def list_scenarios():
    return sorted(p.stem for p in SCENARIOS.glob('*.yaml'))


def load_scenario(name):
    data = yaml.safe_load((SCENARIOS / f'{name}.yaml').read_text()) or {}
    data.setdefault('name', name)
    return {**DEFAULTS, **data}


def prepare_fixtures(out: pathlib.Path, scenario: dict) -> pathlib.Path:
    """Pre-generate echo payload files so shell-based tool mechanisms can `cat` identical bytes."""
    fixtures = out / '_fixtures'
    echo = fixtures / 'echo'
    echo.mkdir(parents=True, exist_ok=True)
    if scenario['kind'] == 'turns' and scenario['tool_calls_per_turn']:
        for turn in range(1, int(scenario['turns']) + 1):
            for idx in range(int(scenario['tool_calls_per_turn'])):
                n = make_nonce(turn, idx)
                path = echo / f'{n}.txt'
                if not path.exists():
                    path.write_text(echo_payload(tool_result_size(scenario, turn), n))
    return fixtures


def versions():
    info = {}
    try:
        lock = json.loads((ROOT / 'package-lock.json').read_text())
        for name in ('ai', '@ai-sdk/openai', '@openai/codex-sdk', '@openai/codex', '@anthropic-ai/claude-agent-sdk', 'zod'):
            entry = lock.get('packages', {}).get('node_modules/' + name)
            if entry:
                info[name] = entry.get('version')
    except (OSError, ValueError):
        pass
    try:
        for line in (ROOT / 'requirements.lock').read_text().splitlines():
            if '==' in line:
                name, ver = line.strip().split('==')
                if name in ('google-adk', 'google-genai', 'langgraph', 'langchain-core', 'langchain-openai', 'pydantic-ai-slim', 'openai', 'psutil'):
                    info[name] = ver
    except OSError:
        pass
    try:
        info['node'] = subprocess.run(['node', '--version'], capture_output=True, text=True).stdout.strip()
        info['python'] = subprocess.run([str(PYTHON), '--version'], capture_output=True, text=True).stdout.strip()
    except OSError:
        pass
    return info


def trial(harness: str, scenario: dict, index: str, server: Server, out: pathlib.Path, fixtures: pathlib.Path, uss: bool = False):
    spec = HARNESSES[harness]
    directory = out / scenario['name'] / f'{harness}-{index}'
    directory.mkdir(parents=True)
    (directory / 'codex').mkdir()
    (directory / 'claude').mkdir()
    run_id = f"{scenario['name']}--{harness}-{index}"
    server.register(run_id, scenario, str(fixtures))
    env = {**os.environ,
           'BENCH_URL': f'{server.url}/run/{run_id}', 'BENCH_RUN_ID': run_id, 'BENCH_SCENARIO': json.dumps(scenario),
           'BENCH_FIXTURES': str(fixtures), 'BENCH_HARNESS': harness,
           'HOME': str(directory), 'CODEX_HOME': str(directory / 'codex'), 'CLAUDE_CONFIG_DIR': str(directory / 'claude'),
           'TMPDIR': str(directory), 'XDG_CONFIG_HOME': str(directory / '.config'), 'XDG_CACHE_HOME': str(directory / '.cache'),
           'OTEL_SDK_DISABLED': 'true', 'LANGSMITH_TRACING': 'false', 'LANGCHAIN_TRACING_V2': 'false', 'DO_NOT_TRACK': '1',
           # Outbound traffic to anything but the arena server is captured as stray and refused.
           'HTTP_PROXY': server.url, 'HTTPS_PROXY': server.url, 'ALL_PROXY': server.url,
           'http_proxy': server.url, 'https_proxy': server.url, 'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost',
           'NODE_USE_ENV_PROXY': '1'}
    for key in STRIP_KEYS:
        env.pop(key, None)
    entry = ROOT / spec['entry']
    cmd = [str(PYTHON), str(entry)] if spec['runtime'] == 'python' else ['node', str(entry)]
    err = open(directory / 'stderr.log', 'w')
    started = time.time()
    proc = subprocess.Popen(cmd, cwd=directory, env=env, stdout=subprocess.PIPE, stderr=err, text=True, start_new_session=True)
    sampler = Sampler(proc.pid, directory, uss=uss)
    phases = []
    state = {'phase': 'starting', 'turn': 0, 'bytes': 0}

    def read():
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            event['elapsed'] = time.monotonic() - sampler.start
            phases.append(event)
            state['phase'] = event.get('phase', state['phase'])
            if 'bytes' in event:
                state['bytes'] = event['bytes']
            if 'n' in event:
                state['turn'] = event['n']
            elif 'turn' in event:
                state['turn'] = event['turn']
    threading.Thread(target=read, daemon=True).start()

    stopped = None
    stop = scenario.get('stop') or {}
    timeout = float(scenario['timeout_seconds'])
    while proc.poll() is None:
        rss = sampler.sample(state['phase'], state['turn'], state['bytes'])
        elapsed = time.monotonic() - sampler.start
        if rss > MEMORY_LIMIT or elapsed > timeout:
            stopped = 'memory_limit' if rss > MEMORY_LIMIT else 'timeout'
        elif stop and ((stop.get('turn') and state['turn'] >= stop['turn']) or (stop.get('bytes') and state['bytes'] >= stop['bytes'])):
            stopped = 'concurrency_checkpoint'
        if stopped:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            break
        time.sleep(0.05)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    # Give lingering grandchildren a moment, then make sure nothing from this trial survives.
    for p in sampler.processes():
        try:
            p.kill()
        except psutil.Error:
            pass
    err.close()
    wall = time.monotonic() - sampler.start
    requests = server.ledger.for_run(run_id)
    done = any(e.get('phase') == 'done' for e in phases)
    status = stopped or ('success' if proc.returncode == 0 and done else 'failed')
    if status == 'success' and scenario['kind'] == 'ramp':
        if any(e.get('phase') == 'checkpoint' and not any(q.get('user_bytes') == e['bytes'] for q in requests) for e in phases):
            status = 'completed_with_compaction'
    first_request = min((q['time'] for q in requests if q.get('kind') != 'stray'), default=None)
    timing = {f't_{e["phase"]}': e['elapsed'] for e in phases if e.get('phase') in ('runtime', 'initialized', 'done')}
    timing['t_first_request'] = (first_request - started) if first_request else None
    result = {'started': started, 'harness': harness, 'scenario': scenario['name'], 'scenario_config': scenario, 'index': index,
              'status': status, 'returncode': proc.returncode, 'wall_seconds': wall, 'timing': timing,
              **sampler.summary(), 'write_bytes': None, 'phases': phases, 'samples': sampler.samples,
              'requests': requests, 'issued_tool_calls': server.ledger.issued(run_id)}
    (directory / 'metrics.json').write_text(json.dumps(result, indent=1))
    print(f"{scenario['name']:18} {harness:10} {index:12} {status:26} peak {result['peak_rss_mib']:7.1f} MiB  "
          f"cpu {result['cpu_seconds_sampled']:5.1f}s  wall {wall:5.1f}s  requests {len(requests)}", flush=True)
    return result


def host_snapshot():
    vm, swap = psutil.virtual_memory(), psutil.swap_memory()
    try:
        load = os.getloadavg()[0]
    except (OSError, AttributeError):
        load = None
    return {'available_mib': vm.available / 1024 ** 2, 'total_mib': vm.total / 1024 ** 2,
            'swap_used_mib': swap.used / 1024 ** 2, 'swap_total_mib': swap.total / 1024 ** 2, 'loadavg_1m': load}


def preflight(host):
    """Warn, never block: RSS on a swapping host is noise, and the report must say so."""
    warnings = []
    if host['swap_total_mib'] and host['swap_used_mib'] > 0.5 * host['swap_total_mib']:
        warnings.append(f"swap {host['swap_used_mib']:.0f} of {host['swap_total_mib']:.0f} MiB in use")
    if host['available_mib'] < 0.25 * host['total_mib']:
        warnings.append(f"only {host['available_mib']:.0f} MiB of {host['total_mib']:.0f} MiB available")
    if warnings:
        print('WARNING host under memory pressure: ' + '; '.join(warnings) + '. RSS figures from this run may be skewed.', flush=True)
    return warnings


def run(scenario_names, harnesses=None, repeats=3, instances=None, uss=False, label=None):
    harnesses = harnesses or ORDER
    out = ROOT / 'results' / (label or time.strftime('%Y%m%d-%H%M%S'))
    out.mkdir(parents=True)
    host = host_snapshot()
    host['preflight_warnings'] = preflight(host)
    server = Server()
    results = []
    try:
        for name in scenario_names:
            scenario = load_scenario(name)
            if scenario.get('planned'):
                print(f'{name}: planned scenario, no adapter support yet; skipped', flush=True)
                continue
            fixtures = prepare_fixtures(out, scenario)
            count = int(instances if instances is not None else scenario['instances'])
            for harness in harnesses:
                if not supports(harness, scenario):
                    results.append({'started': time.time(), 'harness': harness, 'scenario': name, 'scenario_config': scenario,
                                    'index': 'n/a', 'status': 'unsupported', 'requests': [], 'phases': [], 'samples': []})
                    print(f'{name:18} {harness:10} unsupported ({scenario["requires"]})', flush=True)
                    continue
                if count:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
                        results.extend(pool.map(lambda i: trial(harness, scenario, f'parallel-{i}', server, out, fixtures, uss), range(count)))
                else:
                    for i in range(int(scenario.get('repeats', repeats))):
                        results.append(trial(harness, scenario, str(i), server, out, fixtures, uss))
            (out / 'results.json').write_text(json.dumps(summary_doc(results, host), indent=1))
    finally:
        (out / 'requests.json').write_text(json.dumps(server.ledger.requests, indent=1))
        (out / 'results.json').write_text(json.dumps(summary_doc(results, host), indent=1))
        server.shutdown()
    return out


def summary_doc(results, host=None):
    return {'machine': platform.platform(), 'ram_bytes': psutil.virtual_memory().total, 'cpu_count': os.cpu_count(),
            'host_at_start': host, 'versions': versions(), 'results': results}
