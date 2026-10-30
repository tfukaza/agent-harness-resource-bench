"""Harness registry: how each adapter is launched and which arena features it can exercise.

`tool_mechanism` records how bench_echo reaches the harness. Unsupported capabilities make a
scenario render as N/A for that harness; the arena never substitutes zero.
"""
HARNESSES = {
    'adk': {
        'label': 'Google ADK (Python)',
        'runtime': 'python', 'entry': 'harnesses/adk/agent.py', 'protocol': 'gemini',
        'tool_mechanism': 'in-process function',
        'capabilities': {'tools': True, 'mcp': True, 'subagent': True, 'skills': False},
    },
    'langgraph': {
        'label': 'LangGraph (Python)',
        'runtime': 'python', 'entry': 'harnesses/langgraph/agent.py', 'protocol': 'chat',
        'tool_mechanism': 'in-process function',
        'capabilities': {'tools': True, 'mcp': True, 'subagent': True, 'skills': False},
    },
    'pydantic': {
        'label': 'Pydantic AI (Python)',
        'runtime': 'python', 'entry': 'harnesses/pydantic/agent.py', 'protocol': 'chat',
        'tool_mechanism': 'in-process function',
        'capabilities': {'tools': True, 'mcp': True, 'subagent': True, 'skills': False},
    },
    'vercel': {
        'label': 'Vercel AI SDK (Node)',
        'runtime': 'node', 'entry': 'harnesses/vercel/agent.mjs', 'protocol': 'chat',
        'tool_mechanism': 'in-process function',
        'capabilities': {'tools': True, 'mcp': True, 'subagent': True, 'skills': False},
    },
    'codex': {
        'label': 'OpenAI Codex SDK (Node + native binary)',
        'runtime': 'node', 'entry': 'harnesses/codex/agent.mjs', 'protocol': 'responses',
        'tool_mechanism': 'built-in shell tool reading a fixture file (SDK has no in-process custom tools)',
        'capabilities': {'tools': True, 'mcp': True, 'subagent': False, 'skills': True},
    },
    'pi': {
        'label': 'Pi coding agent SDK (Node)',
        'runtime': 'node', 'entry': 'harnesses/pi/agent.mjs', 'protocol': 'chat',
        'tool_mechanism': 'in-process custom tool (customTools)',
        'capabilities': {'tools': True, 'mcp': True, 'subagent': False, 'skills': True},
    },
    'claude': {
        'label': 'Claude Agent SDK (Node + native CLI)',
        'runtime': 'node', 'entry': 'harnesses/claude/agent.mjs', 'protocol': 'anthropic',
        'tool_mechanism': 'in-process SDK MCP server (createSdkMcpServer)',
        'capabilities': {'tools': True, 'mcp': True, 'subagent': True, 'skills': True},
    },
}

ORDER = list(HARNESSES)


def supports(harness: str, scenario: dict) -> bool:
    caps = HARNESSES[harness]['capabilities']
    return all(caps.get(req, False) for req in scenario.get('requires', []))
