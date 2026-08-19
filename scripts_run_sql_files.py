"""Runner idempotente de archivos SQL sobre eldojo_db.

Uso:
    python run_sql_files.py <DATABASE_URL> <mode> <file1.sql> [file2.sql ...]

    mode = migration | seed

Para cada fichero .sql:
  - Se lee entero, se eliminan comentarios inline de tipo -- y líneas vacías.
  - Se separa en sentencias por ';' (se respetan strings).
  - Cada sentencia se ejecuta por separado. Errores de tipo
    'Table already exists', 'Duplicate column name', 'Can't DROP ... check that it exists',
    'Duplicate entry' se tratan como OK (idempotencia soft).
  - Cualquier otro error aborta el proceso.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError, OperationalError, IntegrityError


IDEMPOTENT_PATTERNS = (
    re.compile(r"Table\s+'[^']+'\s+already\s+exists", re.I),
    re.compile(r"Duplicate\s+column\s+name", re.I),
    re.compile(r"Can't\s+DROP\s+[^;]+?\s+check\s+that\s+(?:column|table|foreign key|index)\s+exists", re.I),
    re.compile(r"Duplicate\s+entry\s+", re.I),
    re.compile(r"Key\s+column\s+'[^']+'\s+doesn't\s+exist\s+in\s+table", re.I),
    re.compile(r"Multiple\s+primary\s+key\s+defined", re.I),
)


def split_statements(sql: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    sql = sql.replace("\r\n", "\n")
    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if not in_single and not in_double and not in_backtick:
            if ch == "-" and nxt == "-":
                in_line_comment = True
                i += 2
                continue
            if ch == "/" and nxt == "*":
                in_block_comment = True
                i += 2
                continue

        if ch == "'" and not in_double and not in_backtick:
            # Escapado con doble comilla o backslash
            if in_single and nxt == "'":
                buf.append(ch)
                buf.append(nxt)
                i += 2
                continue
            in_single = not in_single
            buf.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single and not in_backtick:
            if in_double and nxt == '"':
                buf.append(ch)
                buf.append(nxt)
                i += 2
                continue
            in_double = not in_double
            buf.append(ch)
            i += 1
            continue
        if ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
            buf.append(ch)
            i += 1
            continue

        if ch == ";" and not in_single and not in_double and not in_backtick:
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def is_idempotent_error(msg: str) -> bool:
    return any(p.search(msg) for p in IDEMPOTENT_PATTERNS)


def run_file(url: str, path: Path, mode: str) -> None:
    raw = path.read_text(encoding="utf-8")
    stmts = split_statements(raw)
    engine = create_engine(url, future=True, isolation_level="AUTOCOMMIT")
    print(f"\n==> [{mode}] {path.name} ({len(stmts)} statements)")
    with engine.connect() as conn:
        for idx, stmt in enumerate(stmts, 1):
            preview = stmt.strip().splitlines()[0][:140] if stmt.strip() else ""
            try:
                conn.execute(text(stmt))
                print(f"    OK {idx:>3}: {preview}")
            except (ProgrammingError, OperationalError, IntegrityError) as e:
                msg = str(e)
                if is_idempotent_error(msg):
                    print(f"    SK {idx:>3}: idempotent skip -> {msg.splitlines()[0][:180]}")
                else:
                    print(f"    !! {idx:>3}: statement failed -> {preview}")
                    print(f"       Error: {msg}")
                    sys.exit(2)
            except Exception as e:  # noqa: BLE001
                print(f"    !! {idx:>3}: unexpected error -> {preview}")
                print(f"       {type(e).__name__}: {e}")
                sys.exit(2)
    print(f"    == done: {path.name}")


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: run_sql_files.py <DB_URL> <migration|seed> <file1.sql> [file2.sql ...]")
        return 2
    url, mode = sys.argv[1], sys.argv[2]
    if mode not in {"migration", "seed"}:
        print("mode must be 'migration' or 'seed'")
        return 2
    files = [Path(p) for p in sys.argv[3:]]
    for f in files:
        if not f.is_file():
            print(f"missing file: {f}")
            return 2
    for f in files:
        run_file(url, f, mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
