"""Connection layer for the local WordPress MySQL database."""

import os
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor


def get_wp_connection():
    """Open a new connection to the WordPress MySQL database.

    Uses Unix socket if WP_DB_SOCKET is set (local dev with LocalWP),
    otherwise falls back to TCP (production with RDS or similar).
    """
    common = {
        "user": os.environ["WP_DB_USER"],
        "password": os.environ["WP_DB_PASSWORD"],
        "database": os.environ["WP_DB_NAME"],
        "cursorclass": DictCursor,
        "charset": "utf8mb4",
    }

    socket = os.environ.get("WP_DB_SOCKET")
    if socket:
        return pymysql.connect(unix_socket=socket, **common)

    return pymysql.connect(
        host=os.environ["WP_DB_HOST"],
        port=int(os.environ["WP_DB_PORT"]),
        **common,
    )


@contextmanager
def wp_cursor():
    """Context manager that yields a dict cursor and handles cleanup."""
    conn = get_wp_connection()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()
