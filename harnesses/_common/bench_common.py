"""Shared pieces for Python adapters: phase emitter, scenario, the echo tool, and the drive loop."""
import asyncio, json, os, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from arena.payloads import echo_payload, ramp_steps, user_prompt  # noqa: E402

SCENARIO = json.loads(os.environ['BENCH_SCENARIO'])
BASE = os.environ['BENCH_URL']


def emit(**event):
    print(json.dumps(event), flush=True)


def bench_echo(size: int, nonce: str) -> str:
    """Return the benchmark echo payload of exactly `size` bytes tagged with `nonce`."""
    return echo_payload(size, nonce)


async def drive(send):
    """Run the scenario's workload through `send(prompt)`, which must complete one agent turn."""
    s = SCENARIO
    emit(phase='initialized')
    await asyncio.sleep(1)
    pause = float(s.get('pause_seconds', 2))
    kind = s.get('kind', 'turns')
    if kind == 'startup':
        await asyncio.sleep(1)
    elif kind == 'idle':
        await asyncio.sleep(float(s.get('idle_seconds', 60)))
    elif kind == 'ramp':
        count = 0
        current_target = None
        for offset, n, target in ramp_steps(s['targets'], s['chunk']):
            if current_target is not None and target != current_target:
                emit(phase='checkpoint', bytes=current_target)
                await asyncio.sleep(pause)
            current_target = target
            await send(user_prompt(offset, n))
            count += 1
            emit(phase='turn', n=count, bytes=offset + n)
        if current_target is not None:
            emit(phase='checkpoint', bytes=current_target)
            await asyncio.sleep(pause)
    else:
        every = int(s.get('checkpoint_every', 0) or 0)
        for t in range(1, int(s['turns']) + 1):
            await send(user_prompt(t, int(s['prompt_bytes'])))
            emit(phase='turn', n=t)
            if every and t % every == 0:
                emit(phase='checkpoint', turn=t)
                await asyncio.sleep(pause)
    emit(phase='done')


def start():
    emit(phase='runtime')
    time.sleep(1)
