"""Transactional application state. Everything here belongs in the persistent data volume."""

from __future__ import annotations

import copy
import json
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Conflict(Exception):
    pass


class Store:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            self.directory.chmod(0o700)
        except OSError:
            pass
        self.path = self.directory / "console.sqlite3"
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS dashboards (
                  id TEXT PRIMARY KEY, name TEXT NOT NULL, definition TEXT NOT NULL,
                  revision INTEGER NOT NULL, share_token TEXT UNIQUE, created REAL NOT NULL, updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS samples (
                  source TEXT NOT NULL, environment INTEGER NOT NULL, kind TEXT NOT NULL,
                  resource TEXT NOT NULL, stamp REAL NOT NULL, metrics TEXT NOT NULL,
                  PRIMARY KEY(source, environment, kind, resource, stamp));
                CREATE INDEX IF NOT EXISTS samples_age ON samples(stamp);
            """)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def setting(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else copy.deepcopy(default)

    def set_setting(self, key, value):
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO settings VALUES (?,?)",
                (key, json.dumps(value, allow_nan=False)),
            )

    def is_pristine(self):
        with self.connect() as db:
            return not db.execute(
                "SELECT 1 FROM settings WHERE key IN ('admin_password','connection') UNION ALL SELECT 1 FROM dashboards LIMIT 1"
            ).fetchone()

    def initialize(self, connection, admin_password):
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM settings WHERE key IN ('admin_password','connection') UNION ALL SELECT 1 FROM dashboards LIMIT 1"
            ).fetchone():
                raise Conflict("This workspace has already been initialized. Sign in to continue.")
            db.executemany(
                "INSERT INTO settings VALUES (?,?)",
                [
                    ("connection", json.dumps(connection)),
                    ("admin_password", json.dumps(admin_password)),
                ],
            )

    @staticmethod
    def unpack(row):
        if not row:
            return None
        value = json.loads(row["definition"])
        value.update(
            id=row["id"],
            revision=row["revision"],
            created_at=row["created"],
            updated_at=row["updated"],
            shared=bool(row["share_token"]),
        )
        return value

    def dashboards(self):
        with self.connect() as db:
            return [
                self.unpack(r) for r in db.execute("SELECT * FROM dashboards ORDER BY updated DESC")
            ]

    def dashboard(self, identity, shared=False):
        query = (
            "SELECT * FROM dashboards WHERE share_token=?"
            if shared
            else "SELECT * FROM dashboards WHERE id=?"
        )
        with self.connect() as db:
            row = db.execute(query, (identity,)).fetchone()
        return self.unpack(row)

    def save_dashboard(self, definition, identity=None, revision=None):
        now = time.time()
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if identity:
                row = db.execute(
                    "SELECT revision FROM dashboards WHERE id=?", (identity,)
                ).fetchone()
                if not row:
                    raise KeyError(identity)
                if revision != row[0]:
                    raise Conflict(
                        "This dashboard changed in another session. Reload it before saving."
                    )
                db.execute(
                    "UPDATE dashboards SET name=?,definition=?,revision=revision+1,updated=? WHERE id=?",
                    (definition["name"], json.dumps(definition, allow_nan=False), now, identity),
                )
            else:
                identity = uuid.uuid4().hex
                db.execute(
                    "INSERT INTO dashboards VALUES (?,?,?,?,?,?,?)",
                    (
                        identity,
                        definition["name"],
                        json.dumps(definition, allow_nan=False),
                        1,
                        None,
                        now,
                        now,
                    ),
                )
        return self.dashboard(identity)

    def delete_dashboard(self, identity, revision):
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision FROM dashboards WHERE id=?", (identity,)).fetchone()
            if not row:
                raise KeyError(identity)
            if revision != row[0]:
                raise Conflict("This dashboard changed. Reload it before deleting.")
            db.execute("DELETE FROM dashboards WHERE id=?", (identity,))

    def share(self, identity, action="enable"):
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT share_token FROM dashboards WHERE id=?", (identity,)
            ).fetchone()
            if not row:
                raise KeyError(identity)
            token = (
                None
                if action == "disable"
                else secrets.token_urlsafe(32)
                if action == "rotate" or not row[0]
                else row[0]
            )
            db.execute("UPDATE dashboards SET share_token=? WHERE id=?", (token, identity))
        return token

    def record(self, rows):
        if rows:
            with self.lock, self.connect() as db:
                db.executemany("INSERT OR IGNORE INTO samples VALUES (?,?,?,?,?,?)", rows)

    def history(self, source, environment, kind, resource, since, limit=360):
        with self.connect() as db:
            rows = db.execute(
                "SELECT stamp,metrics FROM samples WHERE source=? AND environment=? AND kind=? AND resource=? AND stamp>=? ORDER BY stamp",
                (source, environment, kind, resource, since),
            ).fetchall()
        # Projections request raw samples so aggregation precedes downsampling.
        stride = max(1, (len(rows) + limit - 1) // limit) if limit else 1
        selected = rows[::stride]
        if rows and (not selected or selected[-1][0] != rows[-1][0]):
            selected.append(rows[-1])
        return [(r[0], json.loads(r[1])) for r in selected]

    def prune(self, before):
        with self.lock, self.connect() as db:
            db.execute("DELETE FROM samples WHERE stamp < ?", (before,))
