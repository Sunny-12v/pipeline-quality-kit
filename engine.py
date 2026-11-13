"""The database layer. DuckDB reads CSV/Parquet files directly, so no server is needed."""
from pathlib import Path

from .checks import lit, q


class DuckDBEngine:
    def __init__(self):
        import duckdb

        self.con = duckdb.connect(":memory:")

    def register(self, name, path):
        """Make a file queryable as a table called `name`."""
        reader = "read_parquet" if Path(path).suffix.lower() == ".parquet" else "read_csv_auto"
        self.con.execute(
            f"CREATE VIEW {q(name)} AS SELECT * FROM {reader}({lit(str(path))})"
        )

    def scalar(self, sql):
        """Run a query and return its first value."""
        return self.con.execute(sql).fetchone()[0]
