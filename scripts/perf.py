#!/usr/bin/env python3
"""Small fixed-workload runner. This entrypoint never invokes an AI agent."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks import runner  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('coverage')
    worker = commands.add_parser('_worker')
    worker.add_argument('--request')
    paired = commands.add_parser('paired')
    paired.add_argument('--suite', choices=('pr', 'extended'), default='pr')
    paired.add_argument('--images', required=True)
    paired.add_argument('--commits', required=True)
    paired.add_argument('--host-root', required=True)
    paired.add_argument('--output', type=Path, required=True)
    run = commands.add_parser('run')
    run.add_argument('--suite', choices=('pr', 'extended'), default='pr')
    run.add_argument('--profile', choices=('test', 'medium', 'stress'), default='medium')
    run.add_argument('--case')
    run.add_argument('--observations', type=int)
    run.add_argument('--batch-repetitions', type=int)
    run.add_argument('--scale', type=int, choices=(1, 4), default=1)
    run.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'coverage':
            result = runner.coverage()
        elif args.command == '_worker':
            request = json.loads(args.request) if args.request else json.load(sys.stdin)
            request['root'] = Path(request['root'])
            request['root'].mkdir(parents=True)
            result = runner.observe(**request)
        elif args.command == 'paired':
            from benchmarks.paired import run

            result = run(json.loads(args.images), json.loads(args.commits), args.host_root,
                         args.suite, args.output)
        else:
            if args.observations is not None and args.observations <= 0:
                raise ValueError('Observations must be positive')
            if args.batch_repetitions is not None and args.batch_repetitions <= 0:
                raise ValueError('Batch repetitions must be positive')
            result = runner.run(args.suite, args.profile, args.case, args.observations,
                                args.batch_repetitions, args.scale)
            if args.output:
                args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return 0 if result.get('status') != 'FAIL' else 3
    except Exception as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}), file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
