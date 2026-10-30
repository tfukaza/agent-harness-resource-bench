// Claude Agent SDK adapter: one streaming-input session (single CLI process for the whole trial).
// bench_echo is served by an in-process SDK MCP server, the SDK's custom-tool mechanism.
import { base, drive, echoPayload, start } from '../_common/bench_common.mjs';

await start();
const { query, createSdkMcpServer, tool } = await import('@anthropic-ai/claude-agent-sdk');
const { z } = await import('zod');

const server = createSdkMcpServer({
  name: 'bench', version: '1.0.0',
  tools: [tool('bench_echo', 'Return the benchmark echo payload of exactly `size` bytes tagged with `nonce`.',
    { size: z.number(), nonce: z.string() },
    async ({ size, nonce }) => ({ content: [{ type: 'text', text: echoPayload(size, nonce) }] }))],
});

// Outbound user messages: an async generator fed by push().
const outbox = [];
let wakeOut = null, closed = false;
async function* input() {
  for (;;) {
    while (outbox.length) yield outbox.shift();
    if (closed) return;
    await new Promise((resolve) => { wakeOut = resolve; });
  }
}
const push = (message) => { outbox.push(message); if (wakeOut) { const w = wakeOut; wakeOut = null; w(); } };

const session = query({
  prompt: input(),
  options: {
    model: process.env.BENCH_CLAUDE_MODEL ?? 'claude-sonnet-4-5[1m]',
    tools: [], mcpServers: { bench: server }, allowedTools: ['mcp__bench__bench_echo'],
    permissionMode: 'bypassPermissions', allowDangerouslySkipPermissions: true,
    settingSources: [], cwd: process.cwd(),
    env: { ...process.env, ANTHROPIC_BASE_URL: base, ANTHROPIC_API_KEY: 'fake', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: '1', DISABLE_AUTO_COMPACT: '1' },
  },
});

// Inbound SDK messages: one pump, consumers wait for the kind they need.
const inbox = [];
let wakeIn = null, ended = false;
(async () => {
  for await (const message of session) {
    inbox.push(message);
    if (wakeIn) { const w = wakeIn; wakeIn = null; w(); }
  }
  ended = true;
  if (wakeIn) wakeIn();
})();
async function nextMessage() {
  for (;;) {
    if (inbox.length) return inbox.shift();
    if (ended) return null;
    await new Promise((resolve) => { wakeIn = resolve; });
  }
}

// The CLI child is spawned by query() and is resident well within the 1 s pause after
// "initialized"; in streaming-input mode it sends no init message until the first user turn.
await drive(async (prompt) => {
  push({ type: 'user', message: { role: 'user', content: prompt }, parent_tool_use_id: null, session_id: '' });
  for (;;) {
    const message = await nextMessage();
    if (message === null) throw new Error('session ended before the turn completed');
    if (message.type === 'result') {
      if (message.is_error || message.subtype !== 'success') {
        const detail = message.errors ?? message.result ?? message.stop_reason ?? '';
        throw new Error(`claude result ${message.subtype}: ${JSON.stringify(detail).slice(0, 600)}`);
      }
      return;
    }
  }
});
closed = true;
if (wakeOut) wakeOut();
while ((await nextMessage()) !== null) { /* drain until the CLI exits */ }
