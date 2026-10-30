# Agent harness resource bench

A resource-only arena for AI agent harnesses. It measures what a harness costs to run: memory, CPU,
network requests, bytes on the wire, processes, threads, file descriptors, and disk. It does not
measure whether an agent completes tasks well. That is the job of model and harness quality benchmarks.

Every harness talks to a local **scripted fake LLM** that never runs a model. The fake decides, per
request, whether the scenario still owes a tool call for the current turn and answers with a tool call
or deterministic text. All harnesses therefore perform byte-identical work, and the differences that
remain are harness overhead.

## Harnesses

| key | harness | runtime | wire protocol | custom tool mechanism |
|---|---|---|---|---|
| `adk` | Google ADK | Python | Gemini generateContent | in-process function |
| `langgraph` | LangGraph prebuilt ReAct agent | Python | OpenAI Chat Completions | in-process function |
| `pydantic` | Pydantic AI | Python | OpenAI Chat Completions | in-process function |
| `vercel` | Vercel AI SDK `ToolLoopAgent` | Node | OpenAI Chat Completions | in-process function |
| `pi` | Pi coding agent SDK (`@earendil-works/pi-coding-agent`, pi.dev) | Node, one in-process `AgentSession` per trial | OpenAI Chat Completions via a provider registered on `ModelRuntime` | in-process `customTools` entry; built-in tools disabled by the `tools` allowlist |
| `codex` | OpenAI Codex SDK | Node + native binary, one `codex exec` per turn | OpenAI Responses | built-in shell tool that `cat`s a fixture file (the SDK has no in-process custom tools) |
| `claude` | Claude Agent SDK | Node + native CLI, one streaming-input session per trial | Anthropic Messages | in-process SDK MCP server (`createSdkMcpServer`) |

Versions are pinned in `requirements.lock` and `package-lock.json`. `arena/capabilities.py` records
each harness's launch command and which arena features it can exercise; a scenario a harness cannot
run renders as N/A, never as zero.

## Setup

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.lock
npm ci
```

## Run

```sh
.venv/bin/python bench.py list                                   # scenarios and harnesses
.venv/bin/python bench.py run                                    # phase-1 set, 3 repeats, all harnesses
.venv/bin/python bench.py run --scenario tool-loop,idle --harness pydantic,claude --repeats 1
.venv/bin/python bench.py run --scenario all
.venv/bin/python bench.py validate [results/<run>]               # exit 1 on any integrity error
.venv/bin/python bench.py report   [results/<run>]               # rewrite REPORT.md and summary.json
```

Each run writes `results/<timestamp>/` with `results.json` (every sample and ledger entry),
`requests.json`, `validation.json`, `summary.json`, `REPORT.md`, and one directory per trial holding
`stderr.log`, `metrics.json`, and the trial's isolated `HOME`. Copy reports worth keeping to `reports/`.

## Scenarios

| scenario | isolates | headline outputs |
|---|---|---|
| `startup` | import + agent construction, no requests | time to ready, initialized RSS, CPU, processes, threads, fds, files |
| `idle` | 60 s sitting initialised | RSS drift, background CPU, stray network requests |
| `context-ramp` | history growth 4 KiB to 4 MiB in 256 KiB turns | settled RSS per checkpoint, peak, requests per turn, compaction |
| `tool-loop` | 50 turns, one 4 KiB `bench_echo` call each | RSS at turn checkpoints, CPU per turn, tool gap, request KiB per turn, connections, retained disk |
| `concurrency` | five simultaneous 25-turn tool loops | sampled aggregate peak RSS, aggregate disk |
| `long-session` | 200 short text turns | RSS slope per turn, CPU per turn |
| `large-tool-result` | tool results of 4 KiB, 1 MiB, 8 MiB | memory per result byte, truncation, spooling |
| `streaming-hold` | 2000 stream events over about 30 s per turn | CPU per streamed event, RSS while a connection is held |
| `retry-storm` | scripted 429 and 500 responses | retry count, backoff timing, CPU during backoff |
| `skills`, `mcp`, `subagent` | planned; fixtures exist, adapters do not wire them yet | see `scenarios/*.yaml` |

Scenario files are YAML in `scenarios/`. Fields: `kind` (`startup`, `idle`, `ramp`, `turns`), `turns`,
`prompt_bytes`, `tool_calls_per_turn`, `tool_result_bytes` (int or per-turn list), `checkpoint_every`,
`pause_seconds`, `stream: {pieces, interval_ms}`, `errors: [{turn, status, count, retry_after}]`,
`instances`, `stop: {turn|bytes}`, `requires`, `repeats`, `timeout_seconds`, `allow_truncation`.

## What is measured, and how

- **Memory**: summed RSS over the harness's process tree every 50 ms (may double-count shared pages);
  optional USS with `--uss`. "Settled" values are the median of the last ten samples inside a checkpoint
  pause. Peaks are sampled maxima.
- **CPU**: user+system per process keyed by pid and create time, so restarted children are not lost,
  and attributed to the phase current at sample time (`runtime`, `initialized`, `turn`, `checkpoint`).
  Children that live less than one sample interval are missed.
- **Network**: the fake endpoint logs each request's protocol, streaming flag, request and response
  bytes, server-side duration, declared tool names and schema bytes, system prompt bytes, whether
  prompt-cache markers are present, how many earlier tool results the harness still carries, and
  whether the TCP connection is new. `HTTP(S)_PROXY` points at the arena, so any request to another
  host is logged as **stray** and refused. Harnesses that ignore proxy variables can still escape; stray
  counts are a lower bound.
- **Tool gap**: wall time between the arena finishing a tool-call response and the harness's next
  request. This is the harness's own tool dispatch plus serialisation cost, with no model in the loop.
- **Disk**: retained files and bytes in the trial's isolated `HOME` at exit and the sampled peak
  directory size. macOS exposes no per-process write counters.
- **Processes, threads, file descriptors**: maxima over the trial.
- **Host pressure**: host-wide available memory and swap in use are sampled with every tick, and swap
  pageouts are counted over the trial. The report carries a "Host pressure" table and the host state at
  run start; `bench.py run` prints a warning when swap is over half full or less than a quarter of RAM is
  available. RSS from a loaded host is noise, not harness behaviour.
- **Tool result outcome**: each scripted result is classed as complete, truncated, or replaced (the
  harness sent the model a pointer instead, for example after spooling the result to a file).

Known measurement caveats: RSS on macOS excludes pages the kernel has compressed, so an idle process
can read far below its true footprint; compare medians across trials. Scenarios marked
`failure_is_finding` (`context-ramp`, `retry-storm`) report a harness that gives up as a warning with
the stderr reason, because surviving is what they measure.

## Validation

`bench.py validate` checks the captured traffic rather than trusting the adapters: every ramp
checkpoint must appear in a request with the expected list of SHA-256 digests of the user prompts;
every scripted tool call must be issued and its result must reappear complete in a later request;
every completed turn must end in a text request; failed trials are errors. Stray requests and
truncated results where the scenario allows them are warnings, because they are findings.

## Adding a harness

1. Add an entry to `arena/capabilities.py`.
2. Write `harnesses/<key>/agent.py` or `agent.mjs` using `harnesses/_common`. It must emit the phase
   events, register `bench_echo(size, nonce)` through the framework's own tool mechanism, and call
   `drive(send)` where `send(prompt)` completes one agent turn against `BENCH_URL`.
3. If the framework only offers built-in tools, do nothing extra: the arena issues a shell call that
   `cat`s the matching fixture file instead.

## Adding a scenario

Drop a YAML file in `scenarios/`. Server behaviour (tool calls, pacing, errors) is driven entirely by
the scenario, so most new scenarios need no adapter changes.

## Ideas not yet implemented

Memory slope per KiB of history and per tool call; request bytes divided by user bytes as a wire
overhead ratio; prompt-cache prefix stability across turns; compaction trigger size and cost;
cold versus warm startup; hook and permission overhead; cancellation cost (SIGINT mid-stream, orphans,
leftover files); energy via `powermetrics` or RAPL; Linux cgroup `memory.peak` and `cpu.stat` in a
container for ground truth without sampling error.
