import os
import psycopg2
from psycopg2.extras import RealDictCursor
import random

DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    balance INTEGER NOT NULL DEFAULT 0,
                    purchases_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS admins (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    price INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    order_ref TEXT UNIQUE NOT NULL,
                    user_telegram_id BIGINT NOT NULL,
                    product_name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    admin_message_id INTEGER,
                    admin_chat_id BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS topup_requests (
                    id SERIAL PRIMARY KEY,
                    request_ref TEXT UNIQUE NOT NULL,
                    user_telegram_id BIGINT NOT NULL,
                    username TEXT,
                    amount INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    admin_message_id INTEGER,
                    admin_chat_id BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS purchase_history (
                    id SERIAL PRIMARY KEY,
                    user_telegram_id BIGINT NOT NULL,
                    product_name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    purchased_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id SERIAL PRIMARY KEY,
                    user_telegram_id BIGINT NOT NULL,
                    username TEXT,
                    message_text TEXT NOT NULL,
                    admin_message_id INTEGER,
                    admin_chat_id BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
        conn.commit()


def gen_ref(prefix):
    return f"{prefix}-{random.randint(100000, 999999)}"


# ── Users ──────────────────────────────────────────────
def get_or_create_user(telegram_id, username=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
            user = cur.fetchone()
            if user:
                if username and user["username"] != username:
                    cur.execute("UPDATE users SET username = %s WHERE telegram_id = %s", (username, telegram_id))
                    conn.commit()
                return dict(user)
            cur.execute(
                "INSERT INTO users (telegram_id, username) VALUES (%s, %s) RETURNING *",
                (telegram_id, username)
            )
            conn.commit()
            return dict(cur.fetchone())


def get_user(telegram_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def update_balance(telegram_id, delta):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET balance = balance + %s WHERE telegram_id = %s",
                (delta, telegram_id)
            )
            conn.commit()


def increment_purchases(telegram_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET purchases_count = purchases_count + 1 WHERE telegram_id = %s",
                (telegram_id,)
            )
            conn.commit()


# ── Admins ─────────────────────────────────────────────
def is_admin(telegram_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM admins WHERE telegram_id = %s", (telegram_id,))
            return cur.fetchone() is not None


def get_all_admins():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM admins ORDER BY added_at")
            return [dict(r) for r in cur.fetchall()]


def add_admin(telegram_id):
    if is_admin(telegram_id):
        return False
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO admins (telegram_id) VALUES (%s)", (telegram_id,))
            conn.commit()
    return True


def remove_admin(telegram_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM admins WHERE telegram_id = %s RETURNING id", (telegram_id,))
            conn.commit()
            return cur.fetchone() is not None


# ── Products ───────────────────────────────────────────
def get_all_products():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products ORDER BY created_at")
            return [dict(r) for r in cur.fetchall()]


def get_product_by_id(product_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def add_product(name, price, description):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO products (name, price, description) VALUES (%s, %s, %s)",
                (name, price, description)
            )
            conn.commit()


def delete_product(name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM products WHERE name = %s RETURNING id", (name,))
            conn.commit()
            return cur.fetchone() is not None


# ── Orders ─────────────────────────────────────────────
def create_order(user_telegram_id, product_name, price):
    ref = gen_ref("ORD")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO orders (order_ref, user_telegram_id, product_name, price) VALUES (%s,%s,%s,%s) RETURNING *",
                (ref, user_telegram_id, product_name, price)
            )
            conn.commit()
            return dict(cur.fetchone())


def get_order(order_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def update_order_status(order_id, status, admin_message_id=None, admin_chat_id=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE orders SET status=%s, admin_message_id=%s, admin_chat_id=%s WHERE id=%s",
                (status, admin_message_id, admin_chat_id, order_id)
            )
            conn.commit()


# ── Topup Requests ─────────────────────────────────────
def create_topup(user_telegram_id, username, amount):
    ref = gen_ref("TOP")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO topup_requests (request_ref, user_telegram_id, username, amount) VALUES (%s,%s,%s,%s) RETURNING *",
                (ref, user_telegram_id, username, amount)
            )
            conn.commit()
            return dict(cur.fetchone())


def get_topup(topup_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM topup_requests WHERE id = %s", (topup_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def update_topup_status(topup_id, status, admin_message_id=None, admin_chat_id=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE topup_requests SET status=%s, admin_message_id=%s, admin_chat_id=%s WHERE id=%s",
                (status, admin_message_id, admin_chat_id, topup_id)
            )
            conn.commit()


# ── Purchase History ───────────────────────────────────
def add_purchase_history(user_telegram_id, product_name, price):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO purchase_history (user_telegram_id, product_name, price) VALUES (%s,%s,%s)",
                (user_telegram_id, product_name, price)
            )
            conn.commit()


def get_purchase_history(user_telegram_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM purchase_history WHERE user_telegram_id = %s ORDER BY purchased_at DESC",
                (user_telegram_id,)
            )
            return [dict(r) for r in cur.fetchall()]


# ── Support Tickets ────────────────────────────────────
def create_support_ticket(user_telegram_id, username, message_text):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO support_tickets (user_telegram_id, username, message_text) VALUES (%s,%s,%s) RETURNING *",
                (user_telegram_id, username, message_text)
            )
            conn.commit()
            return dict(cur.fetchone())


def update_support_ticket(ticket_id, admin_message_id, admin_chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE support_tickets SET admin_message_id=%s, admin_chat_id=%s WHERE id=%s",
                (admin_message_id, admin_chat_id, ticket_id)
            )
            conn.commit()


def get_ticket_by_admin_msg(admin_message_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM support_tickets WHERE admin_message_id = %s LIMIT 1",
                (admin_message_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
