"""Data-only local campaign and single-case replay driver."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fuzz import novelty, runner, scenario  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('validate', 'run', 'replay'):
        sub = commands.add_parser(name)
        sub.add_argument('file')
        sub.add_argument('--large', action='store_true')
        if name != 'validate':
            sub.add_argument('--output-dir', required=True)
        if name == 'run':
            sub.add_argument('--history', default='.local-data/fuzz/history.json')
            sub.add_argument('--bootstrap', action='store_true')
            sub.add_argument('--acknowledge-missing', action='store_true')
            sub.add_argument('--case-timeout', type=float)
    export = commands.add_parser('history-export')
    export.add_argument('--history', required=True)
    export.add_argument('--output', required=True)
    restore = commands.add_parser('history-import')
    restore.add_argument('file')
    restore.add_argument('--history', required=True)
    commands.add_parser('_worker')
    args = parser.parse_args()
    try:
        if args.command == '_worker':
            request = json.loads(sys.stdin.read(20 * 1024 * 1024 + 1))
            result = runner.worker(request)
        elif args.command in {'history-import', 'history-export'}:
            value = novelty.validate_history(runner.read_json(args.file if args.command == 'history-import' else args.history))
            runner.write_json(args.history if args.command == 'history-import' else args.output, value)
            result = {'status': 'PASSED'}
        else:
            value = runner.read_json(args.file)
            if args.command == 'validate':
                result = scenario.validate(value, large=args.large)
            elif args.command == 'replay':
                result = runner.report([runner.execute_case(value, large=args.large)], value, args.output_dir)
            else:
                result = runner.run(value, args.output_dir, args.history, bootstrap=args.bootstrap,
                    acknowledge_missing=args.acknowledge_missing, large=args.large, timeout=args.case_timeout)
        failed = result.get('status') in {'INVALID', 'FAILED'}
        print(json.dumps(result), file=sys.stderr if failed else sys.stdout)
        return 3 if failed else 0
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({'status': 'INVALID', 'message': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
