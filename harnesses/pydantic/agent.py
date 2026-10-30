"""Pydantic AI adapter: OpenAI Chat Completions wire protocol, in-process tool."""
import asyncio, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / '_common'))
from bench_common import BASE, bench_echo, drive, start

start()


async def main():
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    agent = Agent(OpenAIChatModel('fake', provider=OpenAIProvider(base_url=BASE + '/v1', api_key='fake')))
    agent.tool_plain(bench_echo)
    history = []

    async def send(prompt):
        result = await agent.run(prompt, message_history=history)
        history[:] = result.all_messages()

    await drive(send)


asyncio.run(main())
