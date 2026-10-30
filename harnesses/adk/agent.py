"""Google ADK adapter: LlmAgent + Runner over the Gemini wire protocol, in-process tool."""
import asyncio, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / '_common'))
from bench_common import BASE, bench_echo, drive, start

start()


async def main():
    from google.adk.agents import LlmAgent
    from google.adk.models.google_llm import Gemini
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    model = Gemini(model='gemini-2.5-flash', base_url=BASE, client_kwargs={'api_key': 'fake'})
    agent = LlmAgent(name='bench', model=model, tools=[bench_echo])
    sessions = InMemorySessionService()
    await sessions.create_session(app_name='bench', user_id='u', session_id='s')
    runner = Runner(agent=agent, app_name='bench', session_service=sessions)

    async def send(prompt):
        message = types.Content(role='user', parts=[types.Part(text=prompt)])
        async for _ in runner.run_async(user_id='u', session_id='s', new_message=message):
            pass

    await drive(send)


asyncio.run(main())
