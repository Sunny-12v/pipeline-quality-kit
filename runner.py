"""Reads the YAML, runs every check, and collects pass/fail results."""
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import yaml

from .checks import ConfigError, build_sql


@dataclass
class Result:
    name: str
    check: str
    table: str
    column: str
    failing: int
    passed: bool
    error: str = ""


def load_config(path):
    path = Path(path)
    try:
        cfg = yaml.safe_load(path.read_text()) or {}
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}")
    if not cfg.get("sources") or not cfg.get("checks"):
        raise ConfigError("config needs both 'sources' and 'checks'")
    # File paths in the YAML are relative to the YAML file itself.
    cfg["sources"] = {n: str((path.parent / p).resolve()) for n, p in cfg["sources"].items()}
    return cfg


def run_checks(checks, engine, now=None):
    now = now or datetime.now()
    results = []
    for spec in checks:
        sql = build_sql(spec, now)  # config mistakes stop the whole run early
        name = f"{spec['check']}:{spec['table']}.{spec.get('column', '')}"
        try:
            failing = int(engine.scalar(sql))
            results.append(Result(name, spec["check"], spec["table"],
                                  spec.get("column", ""), failing, failing == 0))
        except Exception as exc:  # bad column name, bad file, etc.
            results.append(Result(name, spec["check"], spec["table"],
                                  spec.get("column", ""), -1, False, str(exc)))
    return results


def run_config(path, engine, now=None):
    cfg = load_config(path)
    for name, file in cfg["sources"].items():
        engine.register(name, file)
    return run_checks(cfg["checks"], engine, now)


def to_dicts(results):
    return [asdict(r) for r in results]
