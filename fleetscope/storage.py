"""Atomic, immutable run snapshots in SQLite."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4
import pandas as pd


class Store:
    def __init__(self, path):
        self.path = str(path)
        with sqlite3.connect(self.path) as db:
            db.execute(
                'CREATE TABLE IF NOT EXISTS runs '
                '(id TEXT PRIMARY KEY, created TEXT, config TEXT, fingerprint TEXT, payload TEXT)'
            )

    def save(self, config, **frames):
        payload = json.dumps(
            {name: df.to_json(orient='table', index=False) for name, df in frames.items()},
            sort_keys=True,
        )
        config = json.dumps(config, sort_keys=True, allow_nan=False)
        fingerprint = hashlib.sha256((config + payload).encode()).hexdigest()
        run_id = str(uuid4())
        with sqlite3.connect(self.path) as db:
            db.execute(
                'INSERT INTO runs VALUES (?,?,?,?,?)',
                (run_id, datetime.now(timezone.utc).isoformat(), config, fingerprint, payload),
            )
        return run_id

    def history(self):
        with sqlite3.connect(self.path) as db:
            return pd.read_sql_query(
                'SELECT id,created,config,fingerprint FROM runs ORDER BY created DESC', db
            )

    def load(self, run_id):
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT payload FROM runs WHERE id=?', (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return json.loads(row[0])
