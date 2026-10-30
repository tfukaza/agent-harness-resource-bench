// Pi coding agent SDK adapter (pi.dev): one in-process AgentSession for the whole trial, driven over
// OpenAI Chat Completions against a provider registered on the ModelRuntime. bench_echo is a customTool,
// the SDK's own custom-tool mechanism; built-in tools are disabled through the `tools` allowlist.
import { base, drive, echoPayload, start } from '../_common/bench_common.mjs';

// No catalog refresh, version check or telemetry: anything else that still leaves is counted as stray.
process.env.PI_OFFLINE = '1';
process.env.PI_SKIP_VERSION_CHECK = '1';
process.env.PI_TELEMETRY = '0';

await start();
const { createAgentSession, ModelRuntime, getAgentDir } = await import('@earendil-works/pi-coding-agent');
const { Type } = await import('typebox');

const agentDir = getAgentDir();   // ~/.pi/agent under the trial's isolated HOME
const modelRuntime = await ModelRuntime.create({ allowModelNetwork: false });
modelRuntime.registerProvider('bench', {
  name: 'Bench arena', baseUrl: base + '/v1', apiKey: 'fake', api: 'openai-completions',
  models: [{ id: 'fake', name: 'fake', reasoning: false, input: ['text'],
             cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
             // Large enough that the 4 MiB ramp (about 1M synthetic tokens) never triggers compaction.
             contextWindow: 100_000_000, maxTokens: 8192 }],
});
const model = modelRuntime.getModel('bench', 'fake');
if (!model) throw new Error('bench model not registered');

const { session } = await createAgentSession({
  cwd: process.cwd(), agentDir, modelRuntime, model, thinkingLevel: 'off',
  tools: ['bench_echo'],
  customTools: [{
    name: 'bench_echo', label: 'Bench echo',
    description: 'Return the benchmark echo payload of exactly `size` bytes tagged with `nonce`.',
    parameters: Type.Object({ size: Type.Number(), nonce: Type.String() }),
    execute: async (_toolCallId, { size, nonce }) => ({ content: [{ type: 'text', text: echoPayload(size, nonce) }], details: {} }),
  }],
});

let lastError = null;
const unsubscribe = session.subscribe((event) => {
  if (event.type === 'message_end' && event.message?.role === 'assistant' && event.message.stopReason === 'error') {
    lastError = event.message.errorMessage ?? 'assistant message ended with stopReason=error';
  }
});

try {
  await drive(async (prompt) => {
    lastError = null;
    await session.prompt(prompt);
    if (lastError) throw new Error(`pi turn failed: ${String(lastError).slice(0, 600)}`);
  });
} finally {
  unsubscribe();
  session.dispose();
}
