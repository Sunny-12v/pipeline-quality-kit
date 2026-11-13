"""Command line: `pqk run checks.yml`. The exit code is what makes CI/Airflow fail."""
import argparse
import json
import sys

from .checks import ConfigError
from .engine import DuckDBEngine
from .runner import run_config, to_dicts


def main(argv=None, engine_factory=DuckDBEngine):
    parser = argparse.ArgumentParser(prog="pqk", description="Data quality checks as code")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run the checks in a YAML file")
    run.add_argument("config")
    run.add_argument("--json", action="store_true", help="print results as JSON")
    args = parser.parse_args(argv)

    try:
        results = run_config(args.config, engine_factory())
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(to_dicts(results), indent=2))
    else:
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            detail = f"error: {r.error}" if r.error else f"{r.failing} failing rows"
            print(f"[{status}] {r.name}  ({detail})")
        bad = sum(not r.passed for r in results)
        print(f"\n{len(results) - bad} passed, {bad} failed")
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
