"""LangGraph adapter: prebuilt ReAct agent over ChatOpenAI, in-process tool."""
import asyncio, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / '_common'))
from bench_common import BASE, bench_echo, drive, start

start()


async def main():
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent
    agent = create_react_agent(ChatOpenAI(model='fake', api_key='fake', base_url=BASE + '/v1'), tools=[tool(bench_echo)])
    history = []

    async def send(prompt):
        history.append({'role': 'user', 'content': prompt})
        result = await agent.ainvoke({'messages': history})
        history[:] = result['messages']

    await drive(send)


asyncio.run(main())
