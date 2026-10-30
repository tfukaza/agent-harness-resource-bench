#!/usr/bin/env python3
"""Generate N skill directories of fixed size for the planned `skills` scenario.

Usage: generate.py <target-dir> <count> [bytes-per-skill]
Each skill is <dir>/skill-<i>/SKILL.md with YAML frontmatter and deterministic filler.
"""
import pathlib, sys

target, count = pathlib.Path(sys.argv[1]), int(sys.argv[2])
size = int(sys.argv[3]) if len(sys.argv) > 3 else 2048
for i in range(count):
    head = f'---\nname: skill-{i}\ndescription: Arena fixture skill {i}; never relevant to any task.\n---\n\n# Skill {i}\n\n'
    filler = f'Deterministic filler for skill {i}. '
    body = (filler * (size // len(filler) + 1))[: max(0, size - len(head))]
    path = target / f'skill-{i}' / 'SKILL.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(head + body)
print(f'wrote {count} skills under {target}')
