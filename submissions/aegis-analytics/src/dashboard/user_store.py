from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from dashboard.paths import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "data" / "dashboard_users.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_user_store() -> None:
    conn = _connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                favorite_symbol TEXT,
                favorite_horizon TEXT,
                chart_style TEXT,
                window_label TEXT,
                show_ma INTEGER,
                ma_fast INTEGER,
                ma_slow INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS user_watchlist (
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                PRIMARY KEY(user_id, symbol),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                horizon TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                expected_return REAL NOT NULL,
                expected_price REAL NOT NULL,
                p_up REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS user_strategies (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                min_return REAL NOT NULL,
                min_p_up REAL NOT NULL,
                max_downside REAL NOT NULL,
                notes TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS trade_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                horizon TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def register_user(username: str, password: str) -> tuple[bool, str]:
    username = username.strip().lower()
    if not username or not password:
        return False, "Username and password are required."
    conn = _connect()
    try:
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hash_password(password)),
            )
            conn.commit()
            return True, "Account created."
        except sqlite3.IntegrityError:
            return False, "Username already exists."
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    username = username.strip().lower()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return None
        if row["password_hash"] != hash_password(password):
            return None
        return {"id": int(row["id"]), "username": str(row["username"])}
    finally:
        conn.close()


def get_or_create_demo_user() -> dict[str, Any]:
    register_user("demo", "demo123")
    user = authenticate_user("demo", "demo123")
    assert user is not None
    return user


def save_preferences(user_id: int, prefs: dict[str, Any]) -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO user_preferences (
                user_id, favorite_symbol, favorite_horizon, chart_style,
                window_label, show_ma, ma_fast, ma_slow
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                favorite_symbol=excluded.favorite_symbol,
                favorite_horizon=excluded.favorite_horizon,
                chart_style=excluded.chart_style,
                window_label=excluded.window_label,
                show_ma=excluded.show_ma,
                ma_fast=excluded.ma_fast,
                ma_slow=excluded.ma_slow
            """,
            (
                user_id,
                prefs.get("favorite_symbol"),
                prefs.get("favorite_horizon"),
                prefs.get("chart_style"),
                prefs.get("window_label"),
                1 if prefs.get("show_ma") else 0,
                prefs.get("ma_fast"),
                prefs.get("ma_slow"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def load_preferences(user_id: int) -> dict[str, Any]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return {}
        return {
            "favorite_symbol": row["favorite_symbol"],
            "favorite_horizon": row["favorite_horizon"],
            "chart_style": row["chart_style"],
            "window_label": row["window_label"],
            "show_ma": bool(row["show_ma"]),
            "ma_fast": row["ma_fast"],
            "ma_slow": row["ma_slow"],
        }
    finally:
        conn.close()


def save_watchlist(user_id: int, symbols: list[str]) -> None:
    cleaned = sorted({s.strip().upper() for s in symbols if s.strip()})
    conn = _connect()
    try:
        conn.execute("DELETE FROM user_watchlist WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT INTO user_watchlist (user_id, symbol) VALUES (?, ?)",
            [(user_id, symbol) for symbol in cleaned],
        )
        conn.commit()
    finally:
        conn.close()


def load_watchlist(user_id: int) -> list[str]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT symbol FROM user_watchlist WHERE user_id = ? ORDER BY symbol",
            (user_id,),
        ).fetchall()
        return [str(row["symbol"]) for row in rows]
    finally:
        conn.close()


def add_prediction_history(user_id: int, payload: dict[str, Any]) -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO prediction_history (
                user_id, symbol, horizon, timeframe, expected_return,
                expected_price, p_up, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                payload.get("symbol"),
                payload.get("horizon"),
                payload.get("timeframe"),
                payload.get("expected_return"),
                payload.get("expected_price"),
                payload.get("p_up"),
                payload.get("created_at"),
            ),
        )
        conn.execute(
            """
            DELETE FROM prediction_history
            WHERE id NOT IN (
                SELECT id FROM prediction_history
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT 100
            )
            AND user_id = ?
            """,
            (user_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def load_prediction_history(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT symbol, horizon, timeframe, expected_return, expected_price, p_up, created_at
            FROM prediction_history
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

