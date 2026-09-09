"""CLI shares exactly the same operation path; JSON in, compact JSON out."""

import argparse
import json
import sys

from .client import Client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("method", choices=["inspect", "discover", "execute", "capture"])
    parser.add_argument("--params", default="{}", help="JSON arguments, or - to read stdin")
    parser.add_argument("--connection", help="Explicit descriptor path for multiple instances")
    args = parser.parse_args()
    try:
        params = json.loads(sys.stdin.read() if args.params == "-" else args.params)
        result = Client(args.connection).call(args.method, params)
        print(json.dumps(result, separators=(",", ":")))
        if isinstance(result, dict) and result.get("ok") is False:
            raise SystemExit(1)
    except (RuntimeError, ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, separators=(",", ":")), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
