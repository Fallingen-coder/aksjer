"""Database-oppsett: kurshistorikk, portefølje og transaksjoner."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "aksjer.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS prices (
                ticker      TEXT NOT NULL,
                date        TEXT NOT NULL,
                open        REAL,
                high        REAL,
                low         REAL,
                close       REAL,
                volume      INTEGER,
                PRIMARY KEY (ticker, date)
            );

            CREATE TABLE IF NOT EXISTS portfolio (
                ticker      TEXT PRIMARY KEY,
                shares      REAL NOT NULL DEFAULT 0,
                avg_cost    REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT NOT NULL DEFAULT (datetime('now')),
                ticker      TEXT NOT NULL,
                action      TEXT NOT NULL CHECK(action IN ('BUY','SELL')),
                shares      REAL NOT NULL,
                price       REAL NOT NULL,
                reason      TEXT
            );

            CREATE TABLE IF NOT EXISTS cash (
                id          INTEGER PRIMARY KEY CHECK(id = 1),
                amount      REAL NOT NULL
            );

            INSERT OR IGNORE INTO cash (id, amount) VALUES (1, 100000);
        """)
    print("Database klar.")


if __name__ == "__main__":
    init_db()
