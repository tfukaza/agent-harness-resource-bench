#!/usr/bin/env python
"""Arena CLI: run scenarios, validate captured traffic, and render reports."""
import argparse, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from arena import runner  # noqa: E402
from arena.capabilities import HARNESSES, ORDER  # noqa: E402


def latest():
    runs = sorted(p for p in (ROOT / 'results').iterdir() if p.is_dir() and (p / 'results.json').exists())
    if not runs:
        sys.exit('no results yet')
    return runs[-1]


def main():
    parser = argparse.ArgumentParser(prog='bench', description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('run', help='run scenarios')
    r.add_argument('--scenario', default='startup,idle,context-ramp,tool-loop,concurrency', help='comma list or "all"')
    r.add_argument('--harness', default=','.join(ORDER), help='comma list')
    r.add_argument('--repeats', type=int, default=3)
    r.add_argument('--instances', type=int, default=None, help='override parallel instance count for instance scenarios')
    r.add_argument('--uss', action='store_true', help='also sample unique set size (slower, may need privileges)')
    r.add_argument('--label', default=None, help='results directory name')
    r.add_argument('--no-report', action='store_true')
    p = sub.add_parser('report', help='render REPORT.md for a results directory')
    p.add_argument('dir', nargs='?')
    v = sub.add_parser('validate', help='check traffic integrity for a results directory')
    v.add_argument('dir', nargs='?')
    sub.add_parser('list', help='list scenarios and harnesses')
    args = parser.parse_args()

    if args.command == 'list':
        print('scenarios:')
        for name in runner.list_scenarios():
            s = runner.load_scenario(name)
            flag = ' (planned)' if s.get('planned') else ''
            print(f"  {name:20} {s.get('description', '')}{flag}")
        print('harnesses:')
        for name, spec in HARNESSES.items():
            print(f"  {name:12} {spec['label']}; tools via {spec['tool_mechanism']}")
        return
    if args.command == 'run':
        names = runner.list_scenarios() if args.scenario == 'all' else args.scenario.split(',')
        out = runner.run(names, args.harness.split(','), args.repeats, args.instances, args.uss, args.label)
        from arena import validate, report
        validate.validate(out)
        if not args.no_report:
            report.render(out)
        print(out)
        return
    out = pathlib.Path(args.dir) if args.dir else latest()
    if args.command == 'validate':
        from arena import validate
        sys.exit(0 if validate.validate(out)['passed'] else 1)
    if args.command == 'report':
        from arena import report
        print(report.render(out))


if __name__ == '__main__':
    main()
