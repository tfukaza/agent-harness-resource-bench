// OpenAI Codex SDK adapter: one `codex exec` per turn over the Responses wire protocol.
// The SDK exposes no in-process custom tools, so the scripted model calls the built-in shell tool
// to `cat` a fixture file whose bytes equal the bench_echo payload.
import { base, drive, start } from '../_common/bench_common.mjs';

await start();
const { Codex } = await import('@openai/codex-sdk');
const codex = new Codex({
  config: {
    model_provider: 'bench', model: 'fake',
    model_providers: { bench: { name: 'bench', base_url: base + '/v1', wire_api: 'responses', requires_openai_auth: false } },
    model_context_window: 10000000, model_auto_compact_token_limit: 9000000,
  },
});
const thread = codex.startThread({ skipGitRepoCheck: true, sandboxMode: 'read-only', approvalPolicy: 'never', workingDirectory: process.cwd() });
await drive(async (prompt) => {
  // thread.run rejects when the turn fails; `error` items are warnings (e.g. unknown model metadata).
  const turn = await thread.run(prompt);
  if (!turn.finalResponse && !turn.items.length) throw new Error('turn produced no items');
});
