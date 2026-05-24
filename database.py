import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store.db")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0,
                purchases_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS admins (
                telegram_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                price REAL NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE,
                user_id INTEGER,
                username TEXT,
                product_name TEXT,
                price REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS topup_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT UNIQUE,
                user_id INTEGER,
                username TEXT,
                amount REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS purchase_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_name TEXT,
                price REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_active', 'true')")


def get_user(telegram_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        return dict(row) if row else None


def create_user(telegram_id, username):
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
            (telegram_id, username or str(telegram_id))
        )


def update_username(telegram_id, username):
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET username = ? WHERE telegram_id = ?",
            (username or str(telegram_id), telegram_id)
        )


def update_user_balance(telegram_id, delta):
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
            (delta, telegram_id)
        )


def increment_purchases(telegram_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET purchases_count = purchases_count + 1 WHERE telegram_id = ?",
            (telegram_id,)
        )


def get_products():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]


def get_product_by_id(product_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return dict(row) if row else None


def add_product(name, price, description):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO products (name, price, description) VALUES (?, ?, ?)",
            (name, price, description)
        )


def delete_product(name):
    with get_db() as conn:
        c = conn.execute("DELETE FROM products WHERE name = ?", (name,))
        return c.rowcount > 0


def create_order(order_id, user_id, username, product_name, price):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO orders (order_id, user_id, username, product_name, price) VALUES (?, ?, ?, ?, ?)",
            (order_id, user_id, username, product_name, price)
        )


def update_order_status(order_id, status):
    with get_db() as conn:
        conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))


def get_order(order_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        return dict(row) if row else None


def create_topup_request(request_id, user_id, username, amount):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO topup_requests (request_id, user_id, username, amount) VALUES (?, ?, ?, ?)",
            (request_id, user_id, username, amount)
        )


def update_topup_status(request_id, status):
    with get_db() as conn:
        conn.execute("UPDATE topup_requests SET status = ? WHERE request_id = ?", (status, request_id))


def get_topup_request(request_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM topup_requests WHERE request_id = ?", (request_id,)).fetchone()
        return dict(row) if row else None


def is_admin(telegram_id):
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM admins WHERE telegram_id = ?", (telegram_id,)).fetchone()
        return row is not None


def add_admin(telegram_id, added_by):
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO admins (telegram_id, added_by) VALUES (?, ?)",
            (telegram_id, added_by)
        )


def remove_admin(telegram_id):
    with get_db() as conn:
        c = conn.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))
        return c.rowcount > 0


def get_admins():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM admins ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]


def add_purchase_history(user_id, product_name, price):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO purchase_history (user_id, product_name, price) VALUES (?, ?, ?)",
            (user_id, product_name, price)
        )


def get_purchase_history(user_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM purchase_history WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_setting(key):
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key, value):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
