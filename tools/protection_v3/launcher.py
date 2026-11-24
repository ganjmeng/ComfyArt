"""CLI entry. It has no synthetic authorization, so it stops before product entry."""
from __future__ import annotations

import argparse
import os
import sys

from tools.protection_v3.declaration import AuthorizationMissing, DeclarationError, reject_probe_and_credentials
from tools.protection_v3.startup import StartupRefused, preflight


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="protection-v3-adapter")
    parser.add_argument("--source-git")
    parser.add_argument("--source-sha256")
    parser.add_argument("--source-path")
    parser.add_argument("--home")
    parser.add_argument("--port", type=int)
    parser.add_argument("--runtime-id")
    parser.add_argument("--authorization-id", default=None)
    return parser


def decide(argv: list[str] | None, env: dict) -> int:
    """Real CLI status. Product entry is connect_product, which this CLI cannot authorize."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if type(code) is int else 2
    try:
        reject_probe_and_credentials(env)
        preflight(
            source_git=args.source_git, source_sha256=args.source_sha256,
            source_path=args.source_path, home=args.home, port=args.port,
            runtime_id=args.runtime_id,
        )
        if not args.authorization_id:
            raise AuthorizationMissing()
        raise DeclarationError("authorization_not_recorded")
    except AuthorizationMissing:
        print("authorization_missing; not started", file=sys.stderr)
        return 3
    except StartupRefused as exc:
        print(f"{exc.code}; not started", file=sys.stderr)
        return 4
    except DeclarationError as exc:
        print(f"{exc.code}; not started", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    return decide(sys.argv[1:] if argv is None else argv, dict(os.environ))


if __name__ == "__main__":
    sys.exit(main())
