#!/usr/bin/env python3
"""Eight offline synthetic workflows; no AI, providers or Docker controller."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks import gates, runner  # noqa: E402


def read(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('warmup', 'run'):
        command = commands.add_parser(name)
        command.add_argument('--revision', required=True)
        command.add_argument('--output', type=Path, required=True)
        if name == 'run':
            command.add_argument('--batches', type=Path, required=True)
    for name in ('batches', 'compare'):
        command = commands.add_parser(name)
        command.add_argument('reference', type=Path)
        command.add_argument('candidate', type=Path)
        command.add_argument('--output', type=Path, required=True)
        if name == 'compare':
            command.add_argument('--confirmation-reference', type=Path)
            command.add_argument('--confirmation-candidate', type=Path)
    args = parser.parse_args()
    try:
        if args.command in {'warmup', 'run'}:
            result = runner.measure(args.revision, batches=read(args.batches) if args.command == 'run' else None)
        elif args.command == 'batches':
            result = runner.common_batch_counts(read(args.reference), read(args.candidate))
        else:
            reference = read(args.reference)
            approved = read(Path(__file__).resolve().parents[1] / 'benchmarks/reference.json')
            if reference.get('revision') != approved['reference_commit'] or reference.get('recipe_hash') != approved['recipe_sha256']:
                raise ValueError('Reference revision or recipe is not the approved pin')
            confirmation = None
            if args.confirmation_reference or args.confirmation_candidate:
                if not (args.confirmation_reference and args.confirmation_candidate):
                    raise ValueError('Both complete confirmation reports are required')
                confirmation = (read(args.confirmation_reference), read(args.confirmation_candidate))
            if confirmation and confirmation[0].get('revision') != approved['reference_commit']:
                raise ValueError('Confirmation reference revision is not approved')
            result = gates.compare_pair(reference, read(args.candidate), confirmation=confirmation)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
        print(json.dumps({'status': result.get('status', 'OK'), 'output': str(args.output)}, sort_keys=True))
        return 2 if result.get('status') == 'CONFIRM' else 3 if result.get('status') in {'FAIL', 'INVALID'} else 0
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({'status': 'INVALID', 'error': str(error)}), file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
