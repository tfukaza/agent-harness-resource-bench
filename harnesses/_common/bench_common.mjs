// Shared pieces for Node adapters. Payload functions must stay byte-identical to arena/payloads.py.
import { setTimeout as sleep } from 'node:timers/promises';

export { sleep };
export const scenario = JSON.parse(process.env.BENCH_SCENARIO);
export const base = process.env.BENCH_URL;

export const emit = (event) => console.log(JSON.stringify(event));

export function userPrompt(index, size) {
  const seed = `BENCH-${String(index).padStart(8, '0')} The quick brown fox reads deterministic text. `;
  return seed.repeat(Math.floor(size / seed.length) + 1).slice(0, size);
}

export function echoPayload(size, nonce) {
  const seed = `ECHO-${nonce} deterministic tool output payload. `;
  return seed.repeat(Math.floor(size / seed.length) + 1).slice(0, size);
}

export function* rampSteps(targets, chunk) {
  let total = 0;
  for (const target of targets) {
    while (total < target) {
      const n = Math.min(chunk, target - total);
      yield [total, n, target];
      total += n;
    }
  }
}

export async function start() {
  emit({ phase: 'runtime' });
  await sleep(1000);
}

export async function drive(send) {
  const s = scenario;
  emit({ phase: 'initialized' });
  await sleep(1000);
  const pause = Number(s.pause_seconds ?? 2) * 1000;
  const kind = s.kind ?? 'turns';
  if (kind === 'startup') {
    await sleep(1000);
  } else if (kind === 'idle') {
    await sleep(Number(s.idle_seconds ?? 60) * 1000);
  } else if (kind === 'ramp') {
    let count = 0, current = null;
    for (const [offset, n, target] of rampSteps(s.targets, s.chunk)) {
      if (current !== null && target !== current) {
        emit({ phase: 'checkpoint', bytes: current });
        await sleep(pause);
      }
      current = target;
      await send(userPrompt(offset, n));
      count += 1;
      emit({ phase: 'turn', n: count, bytes: offset + n });
    }
    if (current !== null) {
      emit({ phase: 'checkpoint', bytes: current });
      await sleep(pause);
    }
  } else {
    const every = Number(s.checkpoint_every ?? 0);
    for (let t = 1; t <= Number(s.turns); t++) {
      await send(userPrompt(t, Number(s.prompt_bytes)));
      emit({ phase: 'turn', n: t });
      if (every && t % every === 0) {
        emit({ phase: 'checkpoint', turn: t });
        await sleep(pause);
      }
    }
  }
  emit({ phase: 'done' });
}
