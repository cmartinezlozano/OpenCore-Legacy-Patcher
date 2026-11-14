#!/usr/bin/env python3
"""Build only from the exact official rc5 app; the previous full-PR build is withdrawn."""
import argparse
from pathlib import Path
from rc5_additive import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rc5-app', type=Path, required=True)
    parser.add_argument('--prepared-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.rc5_app.resolve(), args.prepared_source.resolve(), args.output.resolve())


if __name__ == '__main__':
    main()
