"""Fail-closed launcher for the logical d4a09666 declaration.

Running this module does not start ComfyUI, bind a port, read a secret file,
or exec another interpreter. A complete declaration still stops because no
authorization record exists.
"""
from __future__ import annotations

import argparse
import os
import sys

from tools.protection_v3.declaration import (
    AuthorizationMissing,
    DeclarationError,
    declare,
    reject_probe_and_credentials,
    require_authorization,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="protection-v3-adapter", add_help=True)
    parser.add_argument("--source-git")
    parser.add_argument("--source-sha256")
    parser.add_argument("--home")
    parser.add_argument("--port", type=int)
    parser.add_argument("--runtime-id")
    parser.add_argument("--authorization-id", default=None)
    return parser


def decide(argv: list[str] | None, env: dict) -> int:
    """Return a process status. 0 is not used: this launcher never starts."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if type(code) is int else 2
    try:
        reject_probe_and_credentials(env)
        declare(
            source_git=args.source_git,
            source_sha256=args.source_sha256,
            home=args.home,
            port=args.port,
            runtime_id=args.runtime_id,
        )
        require_authorization(args.authorization_id)
    except AuthorizationMissing:
        print("authorization_missing; not started", file=sys.stderr)
        return 3
    except DeclarationError as exc:
        print(f"{exc.code}; not started", file=sys.stderr)
        return 2
    print("authorization_not_recorded; not started", file=sys.stderr)
    return 3


def main(argv: list[str] | None = None) -> int:
    return decide(sys.argv[1:] if argv is None else argv, dict(os.environ))


if __name__ == "__main__":
    sys.exit(main())
