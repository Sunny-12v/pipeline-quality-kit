# pipeline-quality-kit

Data quality checks as code. Describe your rules in a YAML file, run one command,
and get a pass/fail report. The exit code fails your CI job or Airflow task when data is bad.

## Why this exists
Bad data usually reaches dashboards silently. This tool turns "the data should look like X"
into checks that run automatically, the same way unit tests guard code.

## How it works
`checks.yml -> DuckDB -> pass/fail report -> exit code (0 ok, 1 failed, 2 bad config)`

1. You list source files (CSV or Parquet) and checks in a YAML file.
2. Each check becomes one SQL query that returns the number of rows breaking the rule.
3. DuckDB runs the queries in memory, with no server or setup.
4. 0 failing rows means PASS. Anything else means FAIL, and the command exits with code 1.

## Supported checks
| Check | Fails when |
|---|---|
| `not_null` | the column has NULLs |
| `unique` | a value appears more than once |
| `accepted_values` | a value is not in the allowed list |
| `range` | a value is below `min` or above `max` |
| `foreign_key` | a value has no match in the parent table |
| `freshness` | the newest row is older than `max_age_hours` |

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -v
pqk run example/checks.yml
```
The example data has deliberate problems, so you will see FAIL lines and exit code 1.

## Use it in Airflow or CI
```bash
pqk run checks.yml || exit 1
```
Add `--json` for machine-readable output.

## Project layout
- `pqk/checks.py`: turns each YAML check into SQL
- `pqk/engine.py`: loads files into DuckDB and runs queries
- `pqk/runner.py`: reads the YAML and collects results
- `pqk/cli.py`: the `pqk` command and exit codes
- `tests/`: unit tests run on every push by GitHub Actions
