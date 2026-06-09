import sqlite3
from contextlib import contextmanager
from config import DB_PATH, LEVELS

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

# ── Initialisation ──────────────────────────────────────────────
def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS joueurs (
                user_id     TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                pts_alltime INTEGER DEFAULT 0,
                pts_hebdo   INTEGER DEFAULT 0,
                victoires   INTEGER DEFAULT 0,
                serie       INTEGER DEFAULT 0,   -- victoires consécutives
                badges      TEXT    DEFAULT ''    -- JSON list
            );

            CREATE TABLE IF NOT EXISTS parties (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     TEXT NOT NULL,
                mot         TEXT NOT NULL,
                difficulte  TEXT NOT NULL,
                gagnant_id  TEXT,
                temps_rep   REAL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS defi_du_jour (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL UNIQUE,   -- YYYY-MM-DD
                mot         TEXT NOT NULL,
                difficulte  TEXT NOT NULL,
                gagnant_id  TEXT,
                pts_gagnes  INTEGER
            );

            CREATE TABLE IF NOT EXISTS hebdo_reset (
                id          INTEGER PRIMARY KEY CHECK (id = 1),
                last_reset  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            INSERT OR IGNORE INTO hebdo_reset (id) VALUES (1);
        """)

# ── Joueurs ─────────────────────────────────────────────────────
def get_niveau(pts: int) -> str:
    niveau = LEVELS[0][1]
    for seuil, label in LEVELS:
        if pts >= seuil:
            niveau = label
    return niveau

def upsert_joueur(user_id: str, name: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO joueurs (user_id, name)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET name = excluded.name
        """, (user_id, name))

def add_points(user_id: str, name: str, pts: int) -> dict:
    upsert_joueur(user_id, name)
    with get_conn() as conn:
        conn.execute("""
            UPDATE joueurs
            SET pts_alltime = pts_alltime + ?,
                pts_hebdo   = pts_hebdo   + ?,
                victoires   = victoires   + 1,
                serie       = serie       + 1
            WHERE user_id = ?
        """, (pts, pts, user_id))
        row = conn.execute(
            "SELECT pts_alltime, pts_hebdo, serie FROM joueurs WHERE user_id = ?",
            (user_id,)
        ).fetchone()
    return {
        "pts_alltime": row["pts_alltime"],
        "pts_hebdo":   row["pts_hebdo"],
        "serie":       row["serie"],
        "niveau":      get_niveau(row["pts_alltime"]),
    }

def reset_serie(user_id: str):
    """Appelé quand un joueur rate (optionnel, non utilisé en mode groupe)."""
    with get_conn() as conn:
        conn.execute("UPDATE joueurs SET serie = 0 WHERE user_id = ?", (user_id,))

def add_badge(user_id: str, badge: str):
    import json
    with get_conn() as conn:
        row = conn.execute("SELECT badges FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return
        badges = json.loads(row["badges"]) if row["badges"] else []
        if badge not in badges:
            badges.append(badge)
            conn.execute("UPDATE joueurs SET badges = ? WHERE user_id = ?",
                         (json.dumps(badges), user_id))

# ── Classements ─────────────────────────────────────────────────
def get_classement_hebdo(limit: int = 10) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT name, pts_hebdo AS points, pts_alltime
            FROM joueurs
            WHERE pts_hebdo > 0
            ORDER BY pts_hebdo DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [{"name": r["name"], "points": r["points"], "niveau": get_niveau(r["pts_alltime"])} for r in rows]

def get_classement_alltime(limit: int = 10) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT name, pts_alltime AS points
            FROM joueurs
            WHERE pts_alltime > 0
            ORDER BY pts_alltime DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [{"name": r["name"], "points": r["points"], "niveau": get_niveau(r["points"])} for r in rows]

def get_champion_semaine() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT name, pts_hebdo FROM joueurs
            WHERE pts_hebdo > 0
            ORDER BY pts_hebdo DESC LIMIT 1
        """).fetchone()
    return {"name": row["name"], "pts": row["pts_hebdo"]} if row else None

def reset_hebdo():
    with get_conn() as conn:
        conn.execute("UPDATE joueurs SET pts_hebdo = 0")
        conn.execute("UPDATE hebdo_reset SET last_reset = CURRENT_TIMESTAMP WHERE id = 1")

# ── Défi du jour ─────────────────────────────────────────────────
def save_defi(date: str, mot: str, difficulte: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO defi_du_jour (date, mot, difficulte)
            VALUES (?, ?, ?)
        """, (date, mot, difficulte))

def get_defi(date: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM defi_du_jour WHERE date = ?", (date,)
        ).fetchone()
    return dict(row) if row else None

def set_defi_gagnant(date: str, user_id: str, pts: int):
    with get_conn() as conn:
        conn.execute("""
            UPDATE defi_du_jour
            SET gagnant_id = ?, pts_gagnes = ?
            WHERE date = ? AND gagnant_id IS NULL
        """, (user_id, pts, date))
