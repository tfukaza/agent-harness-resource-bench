// Vercel AI SDK adapter: ToolLoopAgent over OpenAI Chat Completions, in-process tool.
import { base, drive, echoPayload, start } from '../_common/bench_common.mjs';

await start();
const { ToolLoopAgent, tool, stepCountIs } = await import('ai');
const { createOpenAI } = await import('@ai-sdk/openai');
const { z } = await import('zod');

const agent = new ToolLoopAgent({
  model: createOpenAI({ baseURL: base + '/v1', apiKey: 'fake' }).chat('fake'),
  tools: {
    bench_echo: tool({
      description: 'Return the benchmark echo payload of exactly `size` bytes tagged with `nonce`.',
      inputSchema: z.object({ size: z.number(), nonce: z.string() }),
      execute: async ({ size, nonce }) => echoPayload(size, nonce),
    }),
  },
  stopWhen: stepCountIs(1000),
});
const messages = [];
await drive(async (prompt) => {
  messages.push({ role: 'user', content: prompt });
  const result = await agent.generate({ messages });
  // responseMessages spans every step of the tool loop; response.messages holds only the final step.
  messages.push(...result.responseMessages);
});
