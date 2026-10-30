# Agent harness resource benchmark

Run `2026-10-30-phase1-with-pi` on macOS-26.6.2-arm64-arm-64bit; RAM 16.0 GiB; 10 logical CPUs.

Host at start: 6.9 GiB of 16.0 GiB available, swap 0.3 of 1.0 GiB used, load 3.4.

Local scripted fake LLM endpoints only: no inference, no API charges, no accuracy claims. Every harness performs the same scripted turns and tool calls; differences are harness overhead. Memory is summed RSS over the process tree, which can double-count shared pages. CPU is sampled at 20 Hz and can miss short-lived children. Disk counts files retained in the isolated HOME at exit. "Stray" requests are HTTP calls to anything other than the arena endpoint (telemetry, update checks).

Versions: @ai-sdk/openai 4.0.104, @anthropic-ai/claude-agent-sdk 0.3.312, @earendil-works/pi-coding-agent 1.4.0, @openai/codex 0.165.0, @openai/codex-sdk 0.165.0, ai 7.0.155, google-adk 2.13.0, google-genai 2.33.0, langchain-core 1.7.0, langchain-openai 1.7.3, langgraph 1.2.18, node v24.12.0, openai 3.40.0, psutil 7.2.2, pydantic-ai-slim 2.62.0, python Python 3.12.13, zod 4.6.7.

## startup

Import the SDK and construct an agent; no model requests. Isolates runtime and framework initialisation.

| harness | ready s | initialized RSS MiB | peak MiB | CPU s | procs | threads | fds | files | stray req |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adk | 1.27 [1.27–1.33] | 70.2 [70.2–70.3] | 70.3 [70.2–70.3] | 0.33 [0.30–0.33] | 1 [1–1] | 1 [1–1] | 6 [6–6] | 1 [1–1] | 0 [0–0] |
| langgraph | 1.43 [1.43–1.53] | 96.3 [96.2–96.4] | 96.4 [96.3–96.5] | 0.50 [0.49–0.53] | 1 [1–1] | 1 [1–1] | 6 [6–6] | 1 [1–1] | 0 [0–0] |
| pydantic | 1.37 [1.35–1.39] | 80.7 [80.6–80.8] | 80.8 [80.8–81.0] | 0.41 [0.41–0.41] | 1 [1–1] | 1 [1–1] | 6 [6–6] | 1 [1–1] | 0 [0–0] |
| vercel | 1.11 [1.08–1.12] | 75.8 [75.8–76.6] | 75.9 [75.8–76.6] | 0.13 [0.08–0.13] | 1 [1–1] | 7 [7–7] | 12 [12–13] | 1 [1–1] | 0 [0–0] |
| codex | 1.06 [1.05–1.06] | 54.5 [54.4–54.5] | 54.5 [54.4–54.5] | 0.06 [0.05–0.06] | 1 [1–1] | 7 [7–7] | 12 [12–12] | 1 [1–1] | 0 [0–0] |
| pi | 1.31 [1.30–1.31] | 144.1 [143.7–144.5] | 144.1 [143.7–144.5] | 0.42 [0.41–0.43] | 1 [1–1] | 12 [12–12] | 14 [14–15] | 3 [3–3] | 0 [0–0] |
| claude | 1.12 [1.12–1.14] | 279.5 [278.8–280.0] | 279.8 [279.7–281.0] | 0.52 [0.50–0.55] | 5 [2–5] | 25 [24–25] | 44 [25–47] | 4 [4–4] | 0 [0–0] |

## idle

Sit initialised for 60 s without sending a turn. Exposes background CPU, memory drift, and stray network traffic.

| harness | initialized RSS MiB | drift over 60 s MiB | idle CPU s | threads | model req | stray req |
|---|---:|---:|---:|---:|---:|---:|
| adk | 69.4 [69.0–69.9] | 0.00 [0.00–0.00] | 0.04 [0.02–0.06] | 1 [1–1] | 0 [0–0] | 0 [0–0] |
| langgraph | 96.2 [96.2–96.2] | 0.00 [0.00–0.00] | 0.03 [0.02–0.05] | 1 [1–1] | 0 [0–0] | 0 [0–0] |
| pydantic | 80.8 [80.8–80.8] | 0.00 [0.00–0.00] | 0.03 [0.00–0.05] | 1 [1–1] | 0 [0–0] | 0 [0–0] |
| vercel | 76.6 [76.5–76.7] | 0.00 [0.00–0.00] | 0.03 [0.01–0.04] | 7 [7–7] | 0 [0–0] | 0 [0–0] |
| codex | 54.5 [54.5–54.5] | 0.00 [0.00–0.00] | 0.01 [0.01–0.01] | 7 [7–7] | 0 [0–0] | 0 [0–0] |
| pi | 144.9 [144.5–145.2] | 0.00 [0.00–0.00] | 0.05 [0.01–0.08] | 12 [12–12] | 0 [0–0] | 0 [0–0] |
| claude | 278.6 [277.5–279.8] | 3.70 [3.67–3.73] | 0.64 [0.60–0.68] | 25 [25–25] | 0 [0–0] | 0 [0–0] |

## context-ramp

Grow user history through 4 KiB, 256 KiB, 1 MiB and 4 MiB checkpoints in 256 KiB turns; no tools.

| harness | init MiB | 4 KiB | 256 KiB | 1 MiB | 4 MiB | peak MiB | CPU s | wall s | req/turn | full ramp |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adk | 70.2 [70.0–70.2] | 99.1 [98.7–99.2] | 99.2 [99.1–99.9] | 103.0 [102.3–103.1] | 147.7 [146.8–148.1] | 147.7 [146.9–148.1] | 0.64 [0.60–0.66] | 10.8 [10.8–10.9] | 1.00 [1.00–1.00] | 3/3 |
| langgraph | 96.1 [96.0–96.2] | 97.8 [97.7–98.0] | 99.1 [99.1–99.4] | 104.1 [104.0–105.4] | 160.8 [160.4–163.2] | 160.8 [160.4–163.2] | 0.74 [0.72–0.76] | 10.9 [10.9–10.9] | 1.00 [1.00–1.00] | 3/3 |
| pydantic | 80.8 [80.7–80.8] | 82.4 [82.4–82.4] | 82.4 [82.4–82.5] | 85.5 [85.5–86.0] | 130.5 [130.2–130.5] | 130.5 [130.2–130.6] | 0.59 [0.59–0.64] | 10.8 [10.8–10.8] | 1.00 [1.00–1.00] | 3/3 |
| vercel | 76.4 [76.3–76.6] | 79.9 [79.9–80.2] | 80.8 [80.8–81.2] | 120.4 [120.1–123.6] | 180.7 [176.9–181.6] | 180.7 [176.9–181.6] | 0.35 [0.34–0.36] | 10.4 [10.3–10.4] | 1.00 [1.00–1.00] | 3/3 |
| codex | 54.5 [54.5–85.7] | 55.3 [55.2–55.3] | 56.2 [56.1–56.2] | 57.5 [57.5–57.6] | — | 170.7 [168.6–180.2] | 1.04 [0.84–1.26] | 11.4 [11.3–11.6] | 1.18 [1.18–1.18] | 0/3 |
| pi | 144.4 [144.4–144.5] | 151.2 [150.9–151.4] | 174.2 [174.1–175.2] | 185.2 [183.8–185.6] | 295.3 [293.8–300.8] | 295.3 [293.8–300.8] | 0.71 [0.71–0.71] | 10.6 [10.6–10.7] | 1.00 [1.00–1.00] | 3/3 |
| claude | 275.6 [275.5–276.1] | 295.4 [295.4–295.9] | 302.2 [302.0–302.3] | 326.8 [326.7–327.6] | — | 382.0 [361.4–394.1] | 0.81 [0.78–0.91] | 8.5 [8.5–8.5] | 1.00 [1.00–1.00] | 0/3 |

## tool-loop

50 turns, each a scripted bench_echo tool call returning 4 KiB, then a text reply. Isolates per-tool-call harness overhead.

| harness | init MiB | turn 10 MiB | turn 20 MiB | turn 30 MiB | turn 40 MiB | turn 50 MiB | peak MiB | CPU s | CPU ms/turn | wall s | req/turn | tool gap ms | results ok/trunc/repl | req KiB/turn | cache ctl % | new conns | stray req | procs | retained KiB | ok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adk | 70.1 [70.0–70.4] | 99.7 [99.7–100.0] | 100.4 [100.3–100.8] | 101.1 [101.0–101.5] | 101.9 [101.8–102.3] | 102.6 [102.5–103.0] | 102.7 [102.5–103.1] | 1.93 [1.88–1.95] | 39 [38–39] | 14.1 [14.1–14.1] | 2.00 [2.00–2.00] | 13 [13–13] | 150/0/0 | 228.8 [228.8–228.8] | 0 [0–0] | 1 [1–1] | 0 [0–0] | 1 [1–1] | 0.0 [0.0–0.0] | 3/3 |
| langgraph | 96.2 [95.9–96.3] | 100.7 [100.5–100.7] | 103.2 [103.2–103.3] | 104.6 [103.8–104.6] | 105.1 [105.0–106.0] | 105.9 [105.8–107.0] | 105.9 [105.8–107.0] | 1.87 [1.84–1.87] | 37 [37–37] | 14.1 [14.0–14.1] | 2.00 [2.00–2.00] | 13 [13–13] | 150/0/0 | 227.9 [227.9–227.9] | 0 [0–0] | 1 [1–1] | 0 [0–0] | 1 [1–1] | 0.4 [0.4–0.4] | 3/3 |
| pydantic | 80.8 [80.7–80.9] | 82.8 [82.8–82.9] | 83.0 [83.0–83.0] | 83.1 [83.1–83.2] | 83.3 [83.2–83.3] | 83.4 [83.4–83.5] | 83.4 [83.4–83.5] | 1.30 [1.29–1.32] | 26 [26–26] | 13.5 [13.5–13.5] | 2.00 [2.00–2.00] | 8 [8–9] | 150/0/0 | 227.9 [227.9–227.9] | 0 [0–0] | 1 [1–1] | 0 [0–0] | 1 [1–1] | 0.5 [0.5–0.5] | 3/3 |
| vercel | 76.5 [76.2–76.5] | 117.0 [116.9–117.1] | 120.6 [120.3–122.0] | 125.6 [124.7–125.9] | 131.8 [130.9–134.0] | 136.8 [136.0–138.2] | 136.8 [136.0–138.2] | 0.38 [0.37–0.40] | 8 [7–8] | 12.4 [12.4–12.4] | 2.00 [2.00–2.00] | 1 [1–1] | 150/0/0 | 227.9 [227.9–227.9] | 0 [0–0] | 2 [2–2] | 0 [0–0] | 1 [1–1] | 0.0 [0.0–0.0] | 3/3 |
| codex | 54.4 [54.4–54.4] | 57.2 [57.1–57.4] | 58.4 [58.3–58.5] | 58.9 [58.8–59.1] | 59.3 [59.2–59.5] | 60.5 [60.3–60.5] | 177.1 [177.0–181.3] | 4.09 [4.07–4.15] | 82 [81–83] | 17.5 [17.5–17.5] | 2.00 [2.00–2.00] | 45 [45–45] | 150/0/0 | 326.6 [326.6–326.6] | 0 [0–0] | 100 [100–100] | 0 [0–0] | 6 [6–7] | 10399.2 [10375.0–10423.5] | 3/3 |
| pi | 144.5 [144.2–144.9] | 185.1 [184.5–185.6] | 185.6 [185.2–186.2] | 192.1 [192.0–192.8] | 202.2 [200.8–203.2] | 203.5 [201.4–205.3] | 203.5 [201.4–205.3] | 0.88 [0.88–0.90] | 18 [18–18] | 12.7 [12.7–12.8] | 2.00 [2.00–2.00] | 2 [2–2] | 150/0/0 | 232.9 [232.9–232.9] | 0 [0–0] | 5 [2–5] | 0 [0–0] | 1 [1–1] | 296.8 [296.8–296.8] | 3/3 |
| claude | 275.7 [274.4–277.3] | 366.3 [358.7–370.8] | 380.9 [375.2–385.6] | 390.3 [383.2–395.5] | 400.7 [394.7–400.8] | 407.6 [404.8–410.6] | 407.6 [404.8–410.6] | 1.81 [1.80–1.89] | 36 [36–38] | 13.0 [13.0–13.0] | 2.00 [2.00–2.00] | 5 [5–5] | 150/0/0 | 246.6 [246.6–246.6] | 100 [100–100] | 1 [1–1] | 0 [0–0] | 4 [4–5] | 1089.3 [1089.3–1089.3] | 3/3 |

Tool mechanism per harness: adk: in-process function; langgraph: in-process function; pydantic: in-process function; vercel: in-process function; codex: built-in shell tool reading a fixture file (SDK has no in-process custom tools); pi: in-process custom tool (customTools); claude: in-process SDK MCP server (createSdkMcpServer).

## concurrency

Five independent instances of a 25-turn tool loop at once. Reports sampled aggregate peak memory and disk.

| harness | init MiB | turn 25 MiB | peak MiB | CPU s | CPU ms/turn | wall s | req/turn | tool gap ms | results ok/trunc/repl | req KiB/turn | cache ctl % | new conns | stray req | procs | retained KiB | ok |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adk | 69.4 [69.1–70.2] | 100.1 [99.8–101.1] | 100.1 [99.8–101.1] | 1.17 [1.13–1.17] | 47 [45–47] | 5.3 [5.3–5.4] | 2.00 [2.00–2.00] | 11 [10–12] | 125/0/0 | 115.0 [115.0–115.0] | 0 [0–0] | 1 [1–1] | 0 [0–0] | 1 [1–1] | 0.0 [0.0–0.0] | 5/5 |
| langgraph | 96.5 [96.1–96.7] | 103.8 [102.3–104.9] | 103.8 [102.3–104.9] | 1.21 [1.17–1.25] | 49 [47–50] | 5.4 [5.4–5.4] | 2.00 [2.00–2.00] | 11 [11–12] | 125/0/0 | 114.4 [114.4–114.4] | 0 [0–0] | 1 [1–1] | 0 [0–0] | 1 [1–1] | 0.4 [0.4–0.4] | 5/5 |
| pydantic | 81.0 [80.9–81.0] | 83.2 [83.1–83.2] | 83.2 [83.2–83.3] | 0.90 [0.87–0.93] | 36 [35–37] | 5.1 [5.0–5.1] | 2.00 [2.00–2.00] | 7 [7–8] | 125/0/0 | 114.4 [114.4–114.4] | 0 [0–0] | 1 [1–1] | 0 [0–0] | 1 [1–1] | 0.5 [0.5–0.5] | 5/5 |
| vercel | 75.9 [75.7–76.2] | 122.6 [120.0–123.9] | 122.6 [120.0–123.9] | 0.23 [0.23–0.24] | 9 [9–9] | 4.3 [4.3–4.3] | 2.00 [2.00–2.00] | 1 [1–1] | 125/0/0 | 114.5 [114.5–114.5] | 0 [0–0] | 2 [2–2] | 0 [0–0] | 1 [1–1] | 0.0 [0.0–0.0] | 5/5 |
| codex | 139.1 [133.5–155.4] | 59.7 [58.9–60.0] | 190.5 [171.3–191.3] | 3.56 [3.39–3.73] | 142 [136–149] | 9.4 [9.3–9.4] | 2.00 [2.00–2.00] | 62 [60–64] | 125/0/0 | 202.1 [202.1–202.1] | 0 [0–0] | 50 [50–50] | 0 [0–0] | 11 [8–12] | 2248.7 [1521.1–5117.9] | 5/5 |
| pi | 147.1 [144.3–150.9] | 191.0 [188.9–199.7] | 191.0 [188.9–199.7] | 0.84 [0.82–0.85] | 33 [33–34] | 4.8 [4.7–4.8] | 2.00 [2.00–2.00] | 2 [2–2] | 125/0/0 | 118.9 [118.9–118.9] | 0 [0–0] | 26 [23–27] | 0 [0–0] | 1 [1–1] | 149.8 [149.8–149.8] | 5/5 |
| claude | 276.8 [275.4–277.5] | 402.6 [393.7–417.9] | 402.6 [393.7–417.9] | 1.70 [1.47–1.75] | 68 [59–70] | 5.0 [5.0–5.0] | 2.00 [2.00–2.00] | 10 [10–11] | 125/0/0 | 125.6 [125.6–125.6] | 100 [100–100] | 1 [1–1] | 0 [0–0] | 10 [4–10] | 551.0 [551.0–551.0] | 5/5 |

Aggregate over 5 simultaneous instances:

| harness | sampled aggregate peak MiB | finished | retained files | retained KiB |
|---|---:|---:|---:|---:|
| adk | 502.2 | 5/5 | 5 | 0.0 |
| langgraph | 518.9 | 5/5 | 5 | 1.9 |
| pydantic | 416.2 | 5/5 | 5 | 2.6 |
| vercel | 611.3 | 5/5 | 5 | 0.0 |
| codex | 850.8 | 5/5 | 334 | 15385.5 |
| pi | 969.4 | 5/5 | 20 | 748.8 |
| claude | 2016.0 | 5/5 | 30 | 2755.2 |

Tool mechanism per harness: adk: in-process function; langgraph: in-process function; pydantic: in-process function; vercel: in-process function; codex: built-in shell tool reading a fixture file (SDK has no in-process custom tools); pi: in-process custom tool (customTools); claude: in-process SDK MCP server (createSdkMcpServer).

## Host pressure

Host-wide free memory, swap and pageouts sampled during each trial. Low free memory or non-zero pageouts mean macOS was compressing or paging, and RSS medians for those trials are noisy.

| scenario | harness | min host free MiB | max swap used MiB | pageouts |
|---|---|---:|---:|---:|
| startup | adk | 7069 [7068–7074] | 258 [258–258] | 0 [0–0] |
| startup | langgraph | 7142 [7069–7151] | 258 [258–258] | 0 [0–0] |
| startup | pydantic | 7144 [7141–7151] | 258 [258–258] | 0 [0–0] |
| startup | vercel | 7163 [7157–7250] | 258 [258–258] | 0 [0–0] |
| startup | codex | 7166 [7136–7249] | 258 [258–258] | 0 [0–0] |
| startup | pi | 7149 [7147–7151] | 258 [258–258] | 0 [0–0] |
| startup | claude | 6971 [6930–7083] | 258 [258–258] | 0 [0–0] |
| idle | adk | 6941 [6925–6956] | 258 [258–258] | 0 [0–0] |
| idle | langgraph | 6906 [6900–6913] | 250 [250–250] | 0 [0–0] |
| idle | pydantic | 6854 [6833–6875] | 250 [250–250] | 0 [0–0] |
| idle | vercel | 6843 [6834–6853] | 250 [250–250] | 0 [0–0] |
| idle | codex | 6862 [6809–6915] | 250 [250–250] | 0 [0–0] |
| idle | pi | 6855 [6854–6856] | 250 [250–250] | 0 [0–0] |
| idle | claude | 6769 [6731–6807] | 250 [250–250] | 0 [0–0] |
| context-ramp | adk | 6728 [6727–6890] | 250 [250–250] | 0 [0–0] |
| context-ramp | langgraph | 6899 [6833–6904] | 250 [250–250] | 0 [0–0] |
| context-ramp | pydantic | 6797 [6744–6846] | 250 [250–250] | 0 [0–0] |
| context-ramp | vercel | 6900 [6869–6904] | 250 [250–250] | 0 [0–0] |
| context-ramp | codex | 6822 [6710–6875] | 250 [250–250] | 0 [0–0] |
| context-ramp | pi | 6678 [6677–6773] | 250 [250–250] | 0 [0–0] |
| context-ramp | claude | 6615 [6552–6664] | 250 [250–250] | 0 [0–0] |
| tool-loop | adk | 6729 [6560–6772] | 250 [250–250] | 0 [0–0] |
| tool-loop | langgraph | 6813 [6561–6813] | 250 [250–250] | 0 [0–0] |
| tool-loop | pydantic | 6769 [6628–6802] | 250 [250–250] | 0 [0–0] |
| tool-loop | vercel | 6799 [6588–6825] | 250 [250–250] | 0 [0–0] |
| tool-loop | codex | 6622 [6610–6824] | 250 [250–250] | 0 [0–0] |
| tool-loop | pi | 6462 [6388–6567] | 250 [250–250] | 0 [0–0] |
| tool-loop | claude | 6397 [6372–6400] | 250 [250–250] | 0 [0–0] |
| concurrency | adk | 6351 [6346–6351] | 250 [250–250] | 0 [0–0] |
| concurrency | langgraph | 6342 [6334–6353] | 250 [250–250] | 0 [0–0] |
| concurrency | pydantic | 6396 [6396–6396] | 250 [250–250] | 0 [0–0] |
| concurrency | vercel | 6350 [6300–6350] | 250 [250–250] | 0 [0–0] |
| concurrency | codex | 6468 [6468–6468] | 250 [250–250] | 0 [0–0] |
| concurrency | pi | 6242 [6242–6242] | 250 [250–250] | 0 [0–0] |
| concurrency | claude | 6286 [6286–6286] | 250 [250–250] | 442368 [442368–442368] |

## Validation

Passed: True. Errors: 0. Warnings: 6.
- warning: context-ramp codex 0: history 4194304 not seen intact on the wire (compacted or dropped)
- warning: context-ramp codex 1: history 4194304 not seen intact on the wire (compacted or dropped)
- warning: context-ramp codex 2: history 4194304 not seen intact on the wire (compacted or dropped)
- warning: context-ramp claude 0: trial ended with status failed: Error: claude result success: "Prompt is too long"
- warning: context-ramp claude 1: trial ended with status failed: Error: claude result success: "Prompt is too long"
- warning: context-ramp claude 2: trial ended with status failed: Error: claude result success: "Prompt is too long"

## Limitations

- Fake usage is synthetic (one token per four user bytes). Cost fields emitted by coding SDKs are estimates, not charges.
- Harnesses that ignore HTTP(S)_PROXY can still reach the real network unseen; stray counts are a lower bound.
- Write-byte counters are unavailable on macOS; retained bytes and sampled peak directory size stand in for write amplification.
- RSS on macOS excludes pages the kernel has compressed; an idle process can read far below its true footprint and grow again when it wakes. Compare medians across trials and prefer Linux cgroup figures for ground truth.
- "results ok/trunc/repl" counts tool results that reached the model complete, truncated, or replaced by a pointer (for example spooled to a file).
- Runtime-only samples precede SDK imports. Native child runtimes often start on the first request, so the initialized column understates coding-harness cost; peak and in-turn samples include children.
- Codex launches one `codex exec` per turn; Claude runs one streaming-input CLI session per trial. Both are the SDKs' documented multi-turn paths, not tuned deployments.
- Host pressure is sampled alongside each trial (see "Host pressure"). Trials whose minimum host free memory dropped low or whose pageouts are non-zero ran on a loaded machine; treat their RSS as noisy and prefer a rerun on a quiet host.

## Trial status

- startup adk 0: success; peak 70.3 MiB; cpu 0.30 s; requests 0; stray 0; retained 0 bytes; host free min 7068 MiB.
- startup adk 1: success; peak 70.3 MiB; cpu 0.33 s; requests 0; stray 0; retained 0 bytes; host free min 7069 MiB.
- startup adk 2: success; peak 70.2 MiB; cpu 0.33 s; requests 0; stray 0; retained 0 bytes; host free min 7074 MiB.
- startup langgraph 0: success; peak 96.5 MiB; cpu 0.53 s; requests 0; stray 0; retained 399 bytes; host free min 7069 MiB.
- startup langgraph 1: success; peak 96.4 MiB; cpu 0.50 s; requests 0; stray 0; retained 399 bytes; host free min 7151 MiB.
- startup langgraph 2: success; peak 96.3 MiB; cpu 0.49 s; requests 0; stray 0; retained 399 bytes; host free min 7142 MiB.
- startup pydantic 0: success; peak 81.0 MiB; cpu 0.41 s; requests 0; stray 0; retained 0 bytes; host free min 7144 MiB.
- startup pydantic 1: success; peak 80.8 MiB; cpu 0.41 s; requests 0; stray 0; retained 0 bytes; host free min 7151 MiB.
- startup pydantic 2: success; peak 80.8 MiB; cpu 0.41 s; requests 0; stray 0; retained 0 bytes; host free min 7141 MiB.
- startup vercel 0: success; peak 75.9 MiB; cpu 0.08 s; requests 0; stray 0; retained 0 bytes; host free min 7157 MiB.
- startup vercel 1: success; peak 76.6 MiB; cpu 0.13 s; requests 0; stray 0; retained 0 bytes; host free min 7163 MiB.
- startup vercel 2: success; peak 75.8 MiB; cpu 0.13 s; requests 0; stray 0; retained 0 bytes; host free min 7250 MiB.
- startup codex 0: success; peak 54.5 MiB; cpu 0.05 s; requests 0; stray 0; retained 0 bytes; host free min 7249 MiB.
- startup codex 1: success; peak 54.4 MiB; cpu 0.06 s; requests 0; stray 0; retained 0 bytes; host free min 7136 MiB.
- startup codex 2: success; peak 54.5 MiB; cpu 0.06 s; requests 0; stray 0; retained 0 bytes; host free min 7166 MiB.
- startup pi 0: success; peak 143.7 MiB; cpu 0.42 s; requests 0; stray 0; retained 4 bytes; host free min 7147 MiB.
- startup pi 1: success; peak 144.5 MiB; cpu 0.43 s; requests 0; stray 0; retained 4 bytes; host free min 7151 MiB.
- startup pi 2: success; peak 144.1 MiB; cpu 0.41 s; requests 0; stray 0; retained 4 bytes; host free min 7149 MiB.
- startup claude 0: success; peak 279.7 MiB; cpu 0.55 s; requests 0; stray 0; retained 895 bytes; host free min 7083 MiB.
- startup claude 1: success; peak 279.8 MiB; cpu 0.50 s; requests 0; stray 0; retained 895 bytes; host free min 6930 MiB.
- startup claude 2: success; peak 281.0 MiB; cpu 0.52 s; requests 0; stray 0; retained 895 bytes; host free min 6971 MiB.
- idle adk 0: success; peak 69.0 MiB; cpu 0.25 s; requests 0; stray 0; retained 0 bytes; host free min 6956 MiB.
- idle adk 1: success; peak 69.9 MiB; cpu 0.33 s; requests 0; stray 0; retained 0 bytes; host free min 6925 MiB.
- idle langgraph 0: success; peak 96.2 MiB; cpu 0.51 s; requests 0; stray 0; retained 399 bytes; host free min 6913 MiB.
- idle langgraph 1: success; peak 96.2 MiB; cpu 0.52 s; requests 0; stray 0; retained 399 bytes; host free min 6900 MiB.
- idle pydantic 0: success; peak 80.9 MiB; cpu 0.46 s; requests 0; stray 0; retained 0 bytes; host free min 6875 MiB.
- idle pydantic 1: success; peak 80.8 MiB; cpu 0.40 s; requests 0; stray 0; retained 0 bytes; host free min 6833 MiB.
- idle vercel 0: success; peak 76.7 MiB; cpu 0.11 s; requests 0; stray 0; retained 0 bytes; host free min 6853 MiB.
- idle vercel 1: success; peak 76.5 MiB; cpu 0.12 s; requests 0; stray 0; retained 0 bytes; host free min 6834 MiB.
- idle codex 0: success; peak 54.5 MiB; cpu 0.05 s; requests 0; stray 0; retained 0 bytes; host free min 6809 MiB.
- idle codex 1: success; peak 54.5 MiB; cpu 0.06 s; requests 0; stray 0; retained 0 bytes; host free min 6915 MiB.
- idle pi 0: success; peak 144.5 MiB; cpu 0.42 s; requests 0; stray 0; retained 4 bytes; host free min 6856 MiB.
- idle pi 1: success; peak 145.2 MiB; cpu 0.42 s; requests 0; stray 0; retained 4 bytes; host free min 6854 MiB.
- idle claude 0: success; peak 277.7 MiB; cpu 0.75 s; requests 0; stray 0; retained 919 bytes; host free min 6807 MiB.
- idle claude 1: success; peak 280.0 MiB; cpu 0.78 s; requests 0; stray 0; retained 919 bytes; host free min 6731 MiB.
- context-ramp adk 0: success; peak 147.7 MiB; cpu 0.66 s; requests 17; stray 0; retained 0 bytes; host free min 6890 MiB.
- context-ramp adk 1: success; peak 148.1 MiB; cpu 0.60 s; requests 17; stray 0; retained 0 bytes; host free min 6727 MiB.
- context-ramp adk 2: success; peak 146.9 MiB; cpu 0.64 s; requests 17; stray 0; retained 0 bytes; host free min 6728 MiB.
- context-ramp langgraph 0: success; peak 160.4 MiB; cpu 0.74 s; requests 17; stray 0; retained 399 bytes; host free min 6899 MiB.
- context-ramp langgraph 1: success; peak 163.2 MiB; cpu 0.76 s; requests 17; stray 0; retained 399 bytes; host free min 6904 MiB.
- context-ramp langgraph 2: success; peak 160.8 MiB; cpu 0.72 s; requests 17; stray 0; retained 399 bytes; host free min 6833 MiB.
- context-ramp pydantic 0: success; peak 130.6 MiB; cpu 0.59 s; requests 17; stray 0; retained 530 bytes; host free min 6846 MiB.
- context-ramp pydantic 1: success; peak 130.5 MiB; cpu 0.64 s; requests 17; stray 0; retained 530 bytes; host free min 6744 MiB.
- context-ramp pydantic 2: success; peak 130.2 MiB; cpu 0.59 s; requests 17; stray 0; retained 530 bytes; host free min 6797 MiB.
- context-ramp vercel 0: success; peak 180.7 MiB; cpu 0.34 s; requests 17; stray 0; retained 0 bytes; host free min 6900 MiB.
- context-ramp vercel 1: success; peak 181.6 MiB; cpu 0.35 s; requests 17; stray 0; retained 0 bytes; host free min 6904 MiB.
- context-ramp vercel 2: success; peak 176.9 MiB; cpu 0.36 s; requests 17; stray 0; retained 0 bytes; host free min 6869 MiB.
- context-ramp codex 0: completed_with_compaction; peak 168.6 MiB; cpu 1.26 s; requests 20; stray 0; retained 21396273 bytes; host free min 6875 MiB.
- context-ramp codex 1: completed_with_compaction; peak 180.2 MiB; cpu 1.04 s; requests 20; stray 0; retained 21388032 bytes; host free min 6710 MiB.
- context-ramp codex 2: completed_with_compaction; peak 170.7 MiB; cpu 0.84 s; requests 20; stray 0; retained 21371551 bytes; host free min 6822 MiB.
- context-ramp pi 0: success; peak 293.8 MiB; cpu 0.71 s; requests 17; stray 0; retained 4209840 bytes; host free min 6773 MiB.
- context-ramp pi 1: success; peak 295.3 MiB; cpu 0.71 s; requests 17; stray 0; retained 4209841 bytes; host free min 6678 MiB.
- context-ramp pi 2: success; peak 300.8 MiB; cpu 0.71 s; requests 17; stray 0; retained 4209839 bytes; host free min 6677 MiB.
- context-ramp claude 0: failed; peak 361.4 MiB; cpu 0.78 s; requests 15; stray 0; retained 11615050 bytes; host free min 6552 MiB.
- context-ramp claude 1: failed; peak 394.1 MiB; cpu 0.91 s; requests 15; stray 0; retained 11615050 bytes; host free min 6615 MiB.
- context-ramp claude 2: failed; peak 382.0 MiB; cpu 0.81 s; requests 15; stray 0; retained 11615050 bytes; host free min 6664 MiB.
- tool-loop adk 0: success; peak 103.1 MiB; cpu 1.93 s; requests 100; stray 0; retained 0 bytes; host free min 6729 MiB.
- tool-loop adk 1: success; peak 102.5 MiB; cpu 1.95 s; requests 100; stray 0; retained 0 bytes; host free min 6772 MiB.
- tool-loop adk 2: success; peak 102.7 MiB; cpu 1.88 s; requests 100; stray 0; retained 0 bytes; host free min 6560 MiB.
- tool-loop langgraph 0: success; peak 105.9 MiB; cpu 1.84 s; requests 100; stray 0; retained 399 bytes; host free min 6561 MiB.
- tool-loop langgraph 1: success; peak 107.0 MiB; cpu 1.87 s; requests 100; stray 0; retained 399 bytes; host free min 6813 MiB.
- tool-loop langgraph 2: success; peak 105.8 MiB; cpu 1.87 s; requests 100; stray 0; retained 399 bytes; host free min 6813 MiB.
- tool-loop pydantic 0: success; peak 83.5 MiB; cpu 1.29 s; requests 100; stray 0; retained 530 bytes; host free min 6802 MiB.
- tool-loop pydantic 1: success; peak 83.4 MiB; cpu 1.30 s; requests 100; stray 0; retained 530 bytes; host free min 6628 MiB.
- tool-loop pydantic 2: success; peak 83.4 MiB; cpu 1.32 s; requests 100; stray 0; retained 530 bytes; host free min 6769 MiB.
- tool-loop vercel 0: success; peak 138.2 MiB; cpu 0.37 s; requests 100; stray 0; retained 0 bytes; host free min 6825 MiB.
- tool-loop vercel 1: success; peak 136.0 MiB; cpu 0.40 s; requests 100; stray 0; retained 0 bytes; host free min 6799 MiB.
- tool-loop vercel 2: success; peak 136.8 MiB; cpu 0.38 s; requests 100; stray 0; retained 0 bytes; host free min 6588 MiB.
- tool-loop codex 0: success; peak 181.3 MiB; cpu 4.15 s; requests 100; stray 0; retained 10624017 bytes; host free min 6622 MiB.
- tool-loop codex 1: success; peak 177.1 MiB; cpu 4.09 s; requests 100; stray 0; retained 10648734 bytes; host free min 6824 MiB.
- tool-loop codex 2: success; peak 177.0 MiB; cpu 4.07 s; requests 100; stray 0; retained 10673666 bytes; host free min 6610 MiB.
- tool-loop pi 0: success; peak 203.5 MiB; cpu 0.88 s; requests 100; stray 0; retained 303872 bytes; host free min 6388 MiB.
- tool-loop pi 1: success; peak 205.3 MiB; cpu 0.90 s; requests 100; stray 0; retained 303872 bytes; host free min 6462 MiB.
- tool-loop pi 2: success; peak 201.4 MiB; cpu 0.88 s; requests 100; stray 0; retained 303872 bytes; host free min 6567 MiB.
- tool-loop claude 0: success; peak 407.6 MiB; cpu 1.81 s; requests 100; stray 0; retained 1115421 bytes; host free min 6400 MiB.
- tool-loop claude 1: success; peak 410.6 MiB; cpu 1.80 s; requests 100; stray 0; retained 1115421 bytes; host free min 6397 MiB.
- tool-loop claude 2: success; peak 404.8 MiB; cpu 1.89 s; requests 100; stray 0; retained 1115421 bytes; host free min 6372 MiB.
- concurrency adk parallel-0: success; peak 101.1 MiB; cpu 1.13 s; requests 50; stray 0; retained 0 bytes; host free min 6346 MiB.
- concurrency adk parallel-1: success; peak 100.0 MiB; cpu 1.17 s; requests 50; stray 0; retained 0 bytes; host free min 6351 MiB.
- concurrency adk parallel-2: success; peak 100.1 MiB; cpu 1.17 s; requests 50; stray 0; retained 0 bytes; host free min 6351 MiB.
- concurrency adk parallel-3: success; peak 99.8 MiB; cpu 1.17 s; requests 50; stray 0; retained 0 bytes; host free min 6346 MiB.
- concurrency adk parallel-4: success; peak 101.1 MiB; cpu 1.13 s; requests 50; stray 0; retained 0 bytes; host free min 6351 MiB.
- concurrency langgraph parallel-0: success; peak 102.3 MiB; cpu 1.17 s; requests 50; stray 0; retained 399 bytes; host free min 6342 MiB.
- concurrency langgraph parallel-1: success; peak 103.8 MiB; cpu 1.21 s; requests 50; stray 0; retained 399 bytes; host free min 6353 MiB.
- concurrency langgraph parallel-2: success; peak 103.5 MiB; cpu 1.21 s; requests 50; stray 0; retained 399 bytes; host free min 6342 MiB.
- concurrency langgraph parallel-3: success; peak 104.4 MiB; cpu 1.21 s; requests 50; stray 0; retained 399 bytes; host free min 6334 MiB.
- concurrency langgraph parallel-4: success; peak 104.9 MiB; cpu 1.25 s; requests 50; stray 0; retained 399 bytes; host free min 6334 MiB.
- concurrency pydantic parallel-0: success; peak 83.3 MiB; cpu 0.91 s; requests 50; stray 0; retained 530 bytes; host free min 6396 MiB.
- concurrency pydantic parallel-1: success; peak 83.2 MiB; cpu 0.90 s; requests 50; stray 0; retained 530 bytes; host free min 6396 MiB.
- concurrency pydantic parallel-2: success; peak 83.2 MiB; cpu 0.87 s; requests 50; stray 0; retained 530 bytes; host free min 6396 MiB.
- concurrency pydantic parallel-3: success; peak 83.2 MiB; cpu 0.87 s; requests 50; stray 0; retained 530 bytes; host free min 6396 MiB.
- concurrency pydantic parallel-4: success; peak 83.2 MiB; cpu 0.93 s; requests 50; stray 0; retained 530 bytes; host free min 6396 MiB.
- concurrency vercel parallel-0: success; peak 121.3 MiB; cpu 0.23 s; requests 50; stray 0; retained 0 bytes; host free min 6350 MiB.
- concurrency vercel parallel-1: success; peak 123.5 MiB; cpu 0.23 s; requests 50; stray 0; retained 0 bytes; host free min 6300 MiB.
- concurrency vercel parallel-2: success; peak 122.6 MiB; cpu 0.24 s; requests 50; stray 0; retained 0 bytes; host free min 6350 MiB.
- concurrency vercel parallel-3: success; peak 123.9 MiB; cpu 0.24 s; requests 50; stray 0; retained 0 bytes; host free min 6350 MiB.
- concurrency vercel parallel-4: success; peak 120.0 MiB; cpu 0.23 s; requests 50; stray 0; retained 0 bytes; host free min 6350 MiB.
- concurrency codex parallel-0: success; peak 191.3 MiB; cpu 3.73 s; requests 50; stray 0; retained 2302642 bytes; host free min 6468 MiB.
- concurrency codex parallel-1: success; peak 173.5 MiB; cpu 3.39 s; requests 50; stray 0; retained 5240762 bytes; host free min 6468 MiB.
- concurrency codex parallel-2: success; peak 190.9 MiB; cpu 3.53 s; requests 50; stray 0; retained 2002388 bytes; host free min 6468 MiB.
- concurrency codex parallel-3: success; peak 171.3 MiB; cpu 3.56 s; requests 50; stray 0; retained 4651368 bytes; host free min 6468 MiB.
- concurrency codex parallel-4: success; peak 190.5 MiB; cpu 3.66 s; requests 50; stray 0; retained 1557594 bytes; host free min 6468 MiB.
- concurrency pi parallel-0: success; peak 190.2 MiB; cpu 0.84 s; requests 50; stray 0; retained 153347 bytes; host free min 6242 MiB.
- concurrency pi parallel-1: success; peak 199.6 MiB; cpu 0.82 s; requests 50; stray 0; retained 153347 bytes; host free min 6242 MiB.
- concurrency pi parallel-2: success; peak 191.0 MiB; cpu 0.85 s; requests 50; stray 0; retained 153347 bytes; host free min 6242 MiB.
- concurrency pi parallel-3: success; peak 188.9 MiB; cpu 0.84 s; requests 50; stray 0; retained 153345 bytes; host free min 6242 MiB.
- concurrency pi parallel-4: success; peak 199.7 MiB; cpu 0.82 s; requests 50; stray 0; retained 153346 bytes; host free min 6242 MiB.
- concurrency claude parallel-0: success; peak 402.6 MiB; cpu 1.68 s; requests 50; stray 0; retained 564274 bytes; host free min 6286 MiB.
- concurrency claude parallel-1: success; peak 404.4 MiB; cpu 1.70 s; requests 50; stray 0; retained 564274 bytes; host free min 6286 MiB.
- concurrency claude parallel-2: success; peak 393.7 MiB; cpu 1.47 s; requests 50; stray 0; retained 564275 bytes; host free min 6286 MiB.
- concurrency claude parallel-3: success; peak 417.9 MiB; cpu 1.72 s; requests 50; stray 0; retained 564274 bytes; host free min 6286 MiB.
- concurrency claude parallel-4: success; peak 397.4 MiB; cpu 1.75 s; requests 50; stray 0; retained 564274 bytes; host free min 6286 MiB.
