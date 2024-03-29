#!/usr/bin/env python3
from __future__ import annotations

import argparse
import errno
import logging
import os.path
import re
import sqlite3
import sys
import tempfile
from typing import IO
from typing import Iterable
from typing import Iterator
from typing import Sequence

__version__ = "0.1.4"
_logger = logging.getLogger(__name__)

EXAMPLES = [
    (
        "Selecting columns",
        r"""echo -e '1 2 3\n4 5 6' | {name} 'SELECT c3, c1 FROM "-"'""",
        "3\t1\n6\t4\n",
    ),
    (
        "Syntax shortcut (SELECT and FROM optional)",
        r"echo -e '1 2 3\n4 5 6' | {name} c3,c1",
        "3\t1\n6\t4\n",
    ),
    (
        "Joining files with stdin (suppose web.log has userid,path and users has userid,name)",
        """cat web.log | {name} 'SELECT "-".c2, users.c2 FROM "-" JOIN users ON "-".c1 = users.c1'""",  # noqa
        "/some/path\talice\n/foo/bar\tbob\n/blah/blah\tbob\n",
    ),
]


def format_examples() -> str:
    lines = []
    for name, cmd, result in EXAMPLES:
        lines.append("  " + name + ":")
        lines.append("    $ " + cmd.format(name=os.path.basename(sys.argv[0])))
        for line in result.splitlines():
            lines.append("    " + line)
        lines.append("")
    return "\n".join(lines)


HELP_TEXT = """\
ShellQuery {version}: Command line SQL on plain text files and standard input.

Example usage:
{examples}
""".format(
    version=__version__, examples=format_examples()
)

QUERY_HELP = """\
A SQL query to run. \
The table names are file names, so `SELECT * FROM "web.log"` reads evey line in the file web.log. \
The special table name "-" denotes standard input. \
The columns are named c1, c2, etc. \
If the FROM clause is omitted, it is assumed to be standard input. \
The beginning SELECT may also be omitted.

See SQLite (https://www.sqlite.org/lang_select.html) for documentation on the SQL language.

Note that SQLite is case insensitive, but ShellQuery expects cases to match on platforms with case \
sensitive file names.
"""

LOAD_ROWS_MAX_BUFFER = 1000


def main() -> None:
    logging.basicConfig()
    parser = argparse.ArgumentParser(
        description=HELP_TEXT, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("query", help=QUERY_HELP)
    parser.add_argument(
        "-d",
        "--delimiter",
        default=r"\s+",
        help="A regular expression for splitting lines into columns. Defaults to whitespace.",
    )
    parser.add_argument(
        "-F",
        "--fixed-string",
        action="store_true",
        default=False,
        help="Interpret delimiter as a fixed string instead of a regex",
    )
    parser.add_argument(
        "-c",
        "--max-columns",
        type=int,
        default=100,
        help=(
            "Maximum number of columns to store. "
            "If splitting by the delimiter would produce too many columns, "
            "the final column will be the entire remainder of the string. "
            'Passing "1" lets you query on whole lines instead of columns. '
            "Note that SQLite bombs out after 999 columns."
        ),
    )
    parser.add_argument(
        "--output-delimiter",
        default="\t",
        help="String to use to separate columns. Defaults to tab.",
    )
    parser.add_argument(
        "-H",
        "--output-header",
        action="store_true",
        default=False,
        help="Include a header row in the output",
    )
    args = parser.parse_args()

    results = execute_query(
        args.query, args.delimiter, args.max_columns, args.fixed_string
    )
    print_output(results, args.output_delimiter, args.output_header)


def load_file(
    connection: sqlite3.Connection,
    table_name: str,
    delimiter: str,
    max_columns: int,
    fixed_string: bool,
) -> None:
    def load(file: IO[str]) -> None:
        rows = read_columns(file, delimiter, max_columns, fixed_string)
        load_rows(connection, table_name, rows)

    if table_name == "-":
        load(sys.stdin)
    else:
        with open(table_name) as f:
            load(f)


def re_split(regex: re.Pattern[str], string: str, maxsplit: int) -> list[str]:
    """Same as regex.split(string, maxsplit), but does not include the text in capturing groups.

    https://docs.python.org/3/library/re.html#re.split
    """
    if regex.match(""):
        raise ValueError("Delimiter matching empty string not supported")
    assert maxsplit > 0
    parts = []
    cur = 0
    for match in regex.finditer(string):
        start, end = match.span()
        assert start < end
        parts.append(string[cur:start])
        cur = end
        if len(parts) >= maxsplit:
            break
    assert cur <= len(string)
    # can be empty if string is empty or there's a match at the end
    parts.append(string[cur:])
    return parts


def read_columns(
    file: Iterable[str],
    delimiter: str,
    max_columns: int,
    fixed: bool,
) -> Iterator[list[str]]:
    """Yield the rows/columns in the given file as a list of lists"""
    col_regex = re.compile(re.escape(delimiter) if fixed else delimiter)
    for line in file:
        if line.endswith("\n"):
            line = line[:-1]
        if line:
            if max_columns > 1:
                yield re_split(col_regex, line, max_columns - 1)
            else:
                yield [line]
        else:
            yield []


def load_rows(
    connection: sqlite3.Connection, table: str, data: Iterable[Sequence[object]]
) -> None:
    """Create `table` from the given iterable of rows `data`"""
    cur_width = 1
    col_fmt = "c{} TEXT"
    create_table_stmt = "CREATE TABLE {} ({})".format(
        quote_identifier(table), col_fmt.format(1)
    )
    connection.execute(create_table_stmt)

    current_rows: list[list[object]] = []

    def flush() -> None:
        placeholders = ",".join("?" * cur_width)
        insert_query = "INSERT INTO {} VALUES ({})".format(
            quote_identifier(table), placeholders
        )
        connection.executemany(insert_query, current_rows)
        del current_rows[:]

    for row in data:
        # Expand table if needed
        while len(row) > cur_width:
            if current_rows:
                flush()
            # sqlite alter table takes constant time, regardless of data already in the table
            # https://www.sqlite.org/lang_altertable.html
            alter_table_statement = "ALTER TABLE {} ADD COLUMN {}".format(
                quote_identifier(table), col_fmt.format(cur_width + 1)
            )
            connection.execute(alter_table_statement)
            cur_width += 1

        padded_row = list(row) + [None] * (cur_width - len(row))
        current_rows.append(padded_row)
        if len(current_rows) >= LOAD_ROWS_MAX_BUFFER:
            flush()
    flush()


def add_from_clause(query: str, table: str) -> str:
    """If the query doesn't have a FROM clause, add it using the given table."""
    # Note: doesn't work when query has FROM, GROUP BY, or ORDER BY as a non-keyword
    if re.search(r"\bFROM\b", query, re.I):
        # already has a from clause
        return query
    else:
        clause = f"FROM {quote_identifier(table)} "
        # These are in order of how they should appear in a proper SQL statement
        key_words = [r"WHERE", r"GROUP\s+BY", r"ORDER\s+BY", "LIMIT"]
        for word in key_words:
            match = re.search(r"\b" + word + r"\b", query, re.I)
            if match:
                # Insert FROM clause before the group/order clause
                start = match.start()
                return query[:start] + clause + query[start:]
        # didn't find GROUP BY or ORDER BY clause, so append to end
        return query + " " + clause


def add_select(query: str) -> str:
    """If the query doesn't start with SELECT or WITH, add it."""
    # Note: doesn't work if there are comments in the beginning of the query
    if re.match(r"\s*(SELECT|WITH)\b", query, re.I):
        return query
    else:
        return "SELECT " + query


def quote_identifier(name: str) -> str:
    if '"' not in name:
        return '"' + name + '"'
    if "`" not in name:
        return "`" + name + "`"
    if "]" not in name:
        return "[" + name + "]"
    raise ValueError(f"Unsupported identifier: {name}")


def execute_query(
    query: str, delimiter: str, max_columns: int, fixed_string: bool
) -> sqlite3.Cursor:
    processed_query = add_from_clause(add_select(query), "-")
    with tempfile.NamedTemporaryFile() as temp_file:
        connection = sqlite3.connect(temp_file.name)
        # Let SQLite tell me what tables I need to load by repeatedly running the query.
        # This is really hacky but it's more robust than trying to regex parse the query.
        # e.g. this correctly handles aliasing
        results: sqlite3.Cursor | None = None
        loaded: set[str] = set()
        while results is None:
            cursor = connection.cursor()
            try:
                cursor.execute(processed_query)
            except sqlite3.OperationalError as e:
                no_such_table = "no such table: "
                msg: str = e.args[0]
                if msg.startswith(no_such_table):
                    table_name = msg[len(no_such_table) :]
                    # SQLite treats "SELECT * FROM foo.log" as database foo, table log
                    # We could try to magically handle this, but SELECT * FROM "foo.log" gives the
                    # same message.
                    error = "Should have already loaded {}. You might need to quote the table name"
                    assert table_name not in loaded, error.format(table_name)
                    load_file(
                        connection, table_name, delimiter, max_columns, fixed_string
                    )
                    loaded.add(table_name)
                else:
                    _logger.error("Failed to execute: %s", processed_query)
                    raise
            else:
                results = cursor
        return results


def print_output(rows: sqlite3.Cursor, delimiter: str, header: bool) -> None:
    def stringify(col: object) -> str:
        if col is None:
            return "NULL"
        else:
            return str(col)

    try:
        if header:
            print(delimiter.join(map(stringify, (col[0] for col in rows.description))))
        for row in rows:
            print(delimiter.join(map(stringify, row)))
    except OSError as e:
        if e.errno == errno.EPIPE:
            # ignore, happens when piping the output to things like `head`
            pass
        else:
            raise


if __name__ == "__main__":
    main()
