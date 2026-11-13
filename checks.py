"""Each check turns one YAML entry into ONE SQL query.

The query returns a single number: how many rows (or problems) break the rule.
0 means the check passes. Anything above 0 means it fails.
"""
from datetime import datetime, timedelta


class ConfigError(Exception):
    """Raised when the YAML file is wrong (missing key, unknown check...)."""


def q(name):
    """Quote a table or column name so odd names cannot break the SQL."""
    return '"' + str(name).replace('"', '""') + '"'


def lit(value):
    """Turn a Python value into a safe SQL literal."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _need(spec, *keys):
    for key in keys:
        if key not in spec:
            raise ConfigError(f"check '{spec.get('check')}' needs '{key}': {spec}")


def not_null(spec, now):
    _need(spec, "table", "column")
    return f"SELECT COUNT(*) FROM {q(spec['table'])} WHERE {q(spec['column'])} IS NULL"


def unique(spec, now):
    _need(spec, "table", "column")
    t, c = q(spec["table"]), q(spec["column"])
    # Counts every row that shares its value with another row.
    return (
        f"SELECT COALESCE(SUM(n), 0) FROM ("
        f"SELECT COUNT(*) AS n FROM {t} WHERE {c} IS NOT NULL "
        f"GROUP BY {c} HAVING COUNT(*) > 1) d"
    )


def accepted_values(spec, now):
    _need(spec, "table", "column", "values")
    vals = ", ".join(lit(v) for v in spec["values"])
    t, c = q(spec["table"]), q(spec["column"])
    return f"SELECT COUNT(*) FROM {t} WHERE {c} IS NOT NULL AND {c} NOT IN ({vals})"


def value_range(spec, now):
    _need(spec, "table", "column")
    if "min" not in spec and "max" not in spec:
        raise ConfigError(f"range check needs 'min' and/or 'max': {spec}")
    t, c = q(spec["table"]), q(spec["column"])
    parts = []
    if "min" in spec:
        parts.append(f"{c} < {lit(spec['min'])}")
    if "max" in spec:
        parts.append(f"{c} > {lit(spec['max'])}")
    return f"SELECT COUNT(*) FROM {t} WHERE " + " OR ".join(parts)


def foreign_key(spec, now):
    _need(spec, "table", "column", "ref_table", "ref_column")
    t, c = q(spec["table"]), q(spec["column"])
    rt, rc = q(spec["ref_table"]), q(spec["ref_column"])
    # Rows in the child table whose value has no match in the parent table.
    return (
        f"SELECT COUNT(*) FROM {t} child LEFT JOIN {rt} parent "
        f"ON child.{c} = parent.{rc} "
        f"WHERE child.{c} IS NOT NULL AND parent.{rc} IS NULL"
    )


def freshness(spec, now):
    _need(spec, "table", "column", "max_age_hours")
    limit = now - timedelta(hours=float(spec["max_age_hours"]))
    cutoff = limit.strftime("%Y-%m-%d %H:%M:%S")
    t, c = q(spec["table"]), q(spec["column"])
    # Fails (returns 1) when the newest row is older than the cutoff, or the table is empty.
    return (
        f"SELECT CASE WHEN MAX({c}) IS NULL OR MAX({c}) < {lit(cutoff)} "
        f"THEN 1 ELSE 0 END FROM {t}"
    )


BUILDERS = {
    "not_null": not_null,
    "unique": unique,
    "accepted_values": accepted_values,
    "range": value_range,
    "foreign_key": foreign_key,
    "freshness": freshness,
}


def build_sql(spec, now=None):
    now = now or datetime.now()
    kind = spec.get("check")
    if kind not in BUILDERS:
        raise ConfigError(f"unknown check '{kind}'. Choose from: {', '.join(BUILDERS)}")
    return BUILDERS[kind](spec, now)
