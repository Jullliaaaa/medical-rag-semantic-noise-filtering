#!/usr/bin/env python3
"""
Deterministic SQL validator for text2sql skill.

Usage:
    python validate_sql.py '{"schema_ddl":"CREATE TABLE ...", "sql":"SELECT ..."}'

Prints a single fenced JSON block:
    {"ok": true|false, "error": "<sqlite error or rule violation>"}

Strategy:
1. Reject multiple statements / DDL / DML up front (cheap, no DB needed).
2. Build the schema in an in-memory sqlite (no data).
3. Run `EXPLAIN <sql>` — this parses & resolves column names without needing data.
4. On sqlite3.Error, return its message so the LLM can fix the draft.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys


FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|ATTACH|DETACH|REPLACE|TRUNCATE|VACUUM|PRAGMA)\b",
    re.IGNORECASE,
)


def _emit(ok: bool, error: str = "") -> int:
    out = {"ok": bool(ok), "error": error}
    sys.stdout.write("```json\n")
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stdout.write("\n```\n")
    return 0 if ok else 1


def validate(schema_ddl: str, sql: str) -> tuple[bool, str]:
    sql_stripped = sql.strip().rstrip(";")
    if not sql_stripped:
        return False, "empty SQL"
    if ";" in sql_stripped:
        return False, "multiple SQL statements not allowed"
    if FORBIDDEN.search(sql_stripped):
        return False, "DDL/DML/PRAGMA not allowed; SELECT only"

    con = sqlite3.connect(":memory:")
    try:
        if schema_ddl:
            try:
                con.executescript(schema_ddl)
            except sqlite3.Error as e:
                return False, f"schema DDL did not parse: {e}"
        try:
            con.execute(f"EXPLAIN {sql_stripped}")
        except sqlite3.Error as e:
            return False, f"SQL did not compile: {e}"
        return True, ""
    finally:
        con.close()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return _emit(False, "usage: validate_sql.py '<json payload>'")
    try:
        payload = json.loads(argv[1])
    except json.JSONDecodeError as e:
        return _emit(False, f"argv JSON invalid: {e}")
    ok, err = validate(str(payload.get("schema_ddl", "")), str(payload.get("sql", "")))
    return _emit(ok, err)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
