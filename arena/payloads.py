"""Deterministic text shared by the server, the validator, and the Python adapters.

The JavaScript twin lives in harnesses/_common/bench_common.mjs and must stay byte-identical.
"""
import hashlib

USER_PREFIX = 'BENCH-'
ECHO_PREFIX = 'ECHO-'


def user_prompt(index: int, size: int) -> str:
    """User text for turn `index` (or byte offset `index` in ramp scenarios), exactly `size` bytes."""
    seed = f'{USER_PREFIX}{index:08d} The quick brown fox reads deterministic text. '
    return (seed * (size // len(seed) + 1))[:size]


def nonce(turn: int, idx: int) -> str:
    return f't{turn}-c{idx}'


def echo_payload(size: int, nonce: str) -> str:
    """Tool result returned by bench_echo, exactly `size` bytes, unique per nonce."""
    seed = f'{ECHO_PREFIX}{nonce} deterministic tool output payload. '
    return (seed * (size // len(seed) + 1))[:size]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def ramp_steps(targets, chunk):
    """Yield (offset, n, target) for the context-ramp workload: chunks of at most `chunk` bytes up to each target."""
    total = 0
    for target in targets:
        while total < target:
            n = min(chunk, target - total)
            yield total, n, target
            total += n


def ramp_expected_hashes(targets, chunk):
    """Map each target size to the list of user-prompt hashes a request at that checkpoint must contain."""
    expected, hashes = {}, []
    for offset, n, target in ramp_steps(targets, chunk):
        hashes.append(sha256(user_prompt(offset, n)))
        expected[offset + n] = list(hashes)
    return expected


def tool_result_size(scenario: dict, turn: int) -> int:
    sizes = scenario.get('tool_result_bytes', 4096)
    if isinstance(sizes, list):
        return int(sizes[min(turn - 1, len(sizes) - 1)])
    return int(sizes)
