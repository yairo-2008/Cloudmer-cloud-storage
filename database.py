__author__ = 'Omer'

import sqlite3
import hashlib
import secrets
import os

DB_PATH = "cloudmer.db"


def get_connection():
    """מחזיר חיבור לדאטאבייס"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # מאפשר גישה לעמודות לפי שם
    return conn


def init_db():
    """
    יוצר את הטבלאות אם לא קיימות.
    קרא לפונקציה הזו פעם אחת בהפעלת השרת.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name   TEXT    NOT NULL,
            email       TEXT    NOT NULL UNIQUE,
            password    TEXT    NOT NULL,
            salt        TEXT    NOT NULL,
            role        TEXT    NOT NULL DEFAULT 'user',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized.")


# ─── עזר: הצפנת סיסמה ───────────────────────────────────────────────────────

def hash_password(password: str, salt: str = None):
    """
    מצפין סיסמה עם salt אקראי.
    מחזיר: (hashed_password, salt)
    """
    if salt is None:
        salt = secrets.token_hex(16)  # salt אקראי חדש
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt


# ─── פעולות על משתמשים ──────────────────────────────────────────────────────

def register_user(full_name: str, email: str, password: str, role: str = "user"):
    """
    רושם משתמש חדש.
    מחזיר: (True, "success") או (False, "הודעת שגיאה")
    """
    hashed_password, salt = hash_password(password)

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (full_name, email, password, salt, role)
            VALUES (?, ?, ?, ?, ?)
        """, (full_name, email, hashed_password, salt, role))
        conn.commit()
        conn.close()
        return True, "User registered successfully."

    except sqlite3.IntegrityError:
        # email כבר קיים (UNIQUE constraint)
        return False, "Email already exists."


def login_user(email: str, password: str):
    """
    בודק אם המשתמש קיים והסיסמה נכונה.
    מחזיר: (True, user_row) או (False, "הודעת שגיאה")
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if user is None:
        return False, "Account not found."

    hashed_input, _ = hash_password(password, salt=user["salt"])
    if hashed_input != user["password"]:
        return False, "Incorrect password."

    return True, user


def get_user_by_email(email: str):
    """מחזיר משתמש לפי אימייל, או None אם לא קיים"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user


def update_role(email: str, new_role: str):
    """
    משנה רמת גישה של משתמש.
    roles אפשריים: 'user', 'admin'
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = ? WHERE email = ?", (new_role, email))
    conn.commit()
    conn.close()


# ─── בדיקה ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    # רישום משתמשים לדוגמה
    print(register_user("Omer Cohen", "omer@test.com", "123456"))
    print(register_user("Admin User", "admin@test.com", "adminpass", role="admin"))
    print(register_user("Omer Cohen", "omer@test.com", "123456"))  # כפול - אמור להיכשל

    # לוגין
    success, result = login_user("omer@test.com", "123456")
    if success:
        print(f"Login OK! Welcome {result['full_name']}, role: {result['role']}")
    else:
        print(f"Login failed: {result}")

    # לוגין עם סיסמה שגויה
    success, result = login_user("omer@test.com", "wrongpass")
    print(f"Wrong password test: {result}")
