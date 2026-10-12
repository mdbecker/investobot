"""Explicit offline synthetic replay; never invokes an AI provider."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fuzz import runner, scenario, triage  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('validate', 'run', 'replay', 'minimize'):
        sub = commands.add_parser(name)
        sub.add_argument('file')
        if name != 'validate':
            sub.add_argument('--output-dir', required=True)
        if name == 'run':
            sub.add_argument('--case-timeout', type=float)
    commands.add_parser('_worker')
    args = parser.parse_args()
    try:
        if args.command == '_worker':
            result = runner.worker(json.loads(sys.stdin.read(20 * 1024 * 1024 + 1)))
        else:
            value = runner.read_json(args.file)
            if args.command == 'validate':
                result = scenario.validate(value) if 'cases' in value else scenario.validate_case(value)
            elif args.command == 'replay':
                result = runner.report([runner.execute_case(value)], value, args.output_dir)
            elif args.command == 'minimize':
                result = triage.minimize(value)
                runner.write_json(Path(args.output_dir) / 'minimized.json', result['case'])
                runner.write_json(Path(args.output_dir) / 'minimization.json', result)
            else:
                result = runner.run(value, args.output_dir, timeout=args.case_timeout)
        failed = result.get('status') in {'INVALID', 'FAILED'}
        print(json.dumps(result), file=sys.stderr if failed else sys.stdout)
        return 3 if failed else 0
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({'status': 'INVALID', 'message': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
