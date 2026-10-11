"""Reservations survive failures, restarts, and unknown provider outcomes."""

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path
import sqlite3

from .study import canonical

NANO = 1_000_000_000


def dollars(value):
    result = Decimal(str(value))*NANO
    if not result.is_finite() or result < 0:
        raise ValueError("Money must be finite and nonnegative")
    return int(result.to_integral_value(rounding=ROUND_CEILING))


def money(value):
    return f"{Decimal(value)/NANO:.6f}"


def cost(config, inp, out):
    return dollars((Decimal(config["input_usd_per_million"])*inp +
                    Decimal(config["output_usd_per_million"])*out)/1_000_000)


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def run_lock(directory):
    import fcntl
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/".lock").open("a") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another process is already using this run directory") from None
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


class BudgetExhausted(RuntimeError):
    pass


class Ledger:
    def __init__(self, directory, manifest):
        self.path = Path(directory)/"ledger.sqlite3"
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS attempts(
            id INTEGER PRIMARY KEY, job TEXT NOT NULL, started TEXT NOT NULL, finished TEXT,
            status TEXT NOT NULL, reserved INTEGER NOT NULL, actual INTEGER, counted_input INTEGER,
            parent_id INTEGER, request TEXT NOT NULL, parsed TEXT, text TEXT, raw TEXT, detail TEXT,
            input_tokens INTEGER, output_tokens INTEGER, assumption_breach INTEGER NOT NULL DEFAULT 0
          );
        """)
        existing = self.db.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()
        if existing and existing[0] != canonical(manifest):
            self.db.close()
            raise ValueError("Frozen manifest changed. Restore the original code/config/tasks to resume; do not overwrite this run.")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('manifest',?)",(canonical(manifest),))
        self.manifest = manifest
        self.limit = dollars(manifest["config"]["budget_usd"])

    def close(self):
        self.db.close()

    def attempts(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM attempts ORDER BY id")]

    def exposure(self):
        return self.db.execute("SELECT COALESCE(SUM(MAX(reserved,COALESCE(actual,0))),0) FROM attempts").fetchone()[0]

    def reserve(self, job, amount, counted_input, request, parent_id=None, retry=False):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            rows = self.db.execute("SELECT status FROM attempts WHERE job=?",(job,)).fetchall()
            if any(r[0]=="valid" for r in rows) or (rows and (not retry or len(rows)>=self.manifest["config"]["max_attempts_per_cell"])):
                self.db.rollback()
                return None
            if self.exposure()+amount > self.limit:
                raise BudgetExhausted("Next request would exceed the $10 reservation cap")
            cursor = self.db.execute("""INSERT INTO attempts(job,started,status,reserved,counted_input,parent_id,request)
                VALUES (?,?,'pending',?,?,?,?)""",(job,now(),amount,counted_input,parent_id,canonical(request)))
            self.db.commit()  # Before any paid request can be sent.
            return cursor.lastrowid
        except BaseException:
            self.db.rollback()
            raise

    def finish(self, attempt, *, status, actual=None, parsed=None, text="", raw=None, detail=None,
               input_tokens=None, output_tokens=None, assumption_breach=False):
        with self.db:
            self.db.execute("""UPDATE attempts SET finished=?,status=?,actual=?,parsed=?,text=?,raw=?,detail=?,
                input_tokens=?,output_tokens=?,assumption_breach=? WHERE id=?""",
                (now(),status,actual,canonical(parsed) if parsed is not None else None,text,
                 canonical(raw) if raw is not None else None,detail,input_tokens,output_tokens,int(assumption_breach),attempt))

    def stop(self, reason):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES ('last_stop',?)",(canonical({"at":now(),"reason":reason}),))


def read_run(directory):
    path = Path(directory)/"ledger.sqlite3"
    if not path.exists():
        raise ValueError(f"No saved run at {directory}")
    db = sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)
    db.row_factory = sqlite3.Row
    try:
        meta = {r[0]:json.loads(r[1]) for r in db.execute("SELECT key,value FROM metadata")}
        return meta, [dict(r) for r in db.execute("SELECT * FROM attempts ORDER BY id")]
    finally:
        db.close()
