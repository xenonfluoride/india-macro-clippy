#!/usr/bin/env python3
"""Strict v2 evaluator. A legacy HTML/audit pair is never publication approval."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'work'))
from newsletter import validate


def evaluate(run, historical=False):
    try:
        validate(Path(run), historical=historical)
        print('PASS: complete review, evidence references, bound semantic verification, prices and exact rendering')
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f'FAIL: {error}')
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--historical', action='store_true', help='Archived replay only; not publication authorization')
    args = parser.parse_args()
    raise SystemExit(evaluate(args.run, args.historical))
