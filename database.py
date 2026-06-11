import json
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
    except Exception:
        conn.rollback()
        raise
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
                serie       INTEGER DEFAULT 0,
                badges      TEXT    DEFAULT ''
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
                date        TEXT NOT NULL UNIQUE,
                mot         TEXT NOT NULL,
                difficulte  TEXT NOT NULL,
                gagnant_id  TEXT,
                pts_gagnes  INTEGER
            );

            CREATE TABLE IF NOT EXISTS hebdo_reset (
                id          INTEGER PRIMARY KEY CHECK (id = 1),
                last_reset  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chats_enregistres (
                chat_id     INTEGER PRIMARY KEY
            );

            INSERT OR IGNORE INTO hebdo_reset (id) VALUES (1);

            CREATE INDEX IF NOT EXISTS idx_pts_hebdo   ON joueurs(pts_hebdo   DESC);
            CREATE INDEX IF NOT EXISTS idx_pts_alltime ON joueurs(pts_alltime DESC);
        """)
    # Migration : colonne victoires_hard (idempotente)
    try:
        with get_conn() as conn:
            conn.execute("ALTER TABLE joueurs ADD COLUMN victoires_hard INTEGER DEFAULT 0")
    except Exception:
        pass

# ── Joueurs ─────────────────────────────────────────────────────
def get_niveau(pts: int) -> str:
    niveau = LEVELS[0][1]
    for seuil, label in LEVELS:
        if pts >= seuil:
            niveau = label
    return niveau

def get_joueur_name(user_id: str) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT name FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
    return row["name"] if row else "Inconnu"

def add_points(user_id: str, name: str, pts: int, difficulte: str = "easy") -> dict:
    hard_incr = 1 if difficulte == "hard" else 0
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO joueurs (user_id, name, pts_alltime, pts_hebdo, victoires, serie, victoires_hard)
            VALUES (?, ?, ?, ?, 1, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name           = excluded.name,
                pts_alltime    = pts_alltime    + ?,
                pts_hebdo      = pts_hebdo      + ?,
                victoires      = victoires      + 1,
                serie          = serie          + 1,
                victoires_hard = victoires_hard + ?
        """, (user_id, name, pts, pts, hard_incr, pts, pts, hard_incr))
        row = conn.execute(
            "SELECT pts_alltime, pts_hebdo, serie, victoires, victoires_hard FROM joueurs WHERE user_id = ?",
            (user_id,)
        ).fetchone()
    return {
        "pts_alltime":    row["pts_alltime"],
        "pts_hebdo":      row["pts_hebdo"],
        "serie":          row["serie"],
        "victoires":      row["victoires"],
        "victoires_hard": row["victoires_hard"],
        "niveau":         get_niveau(row["pts_alltime"]),
    }

def get_profil(user_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["badges"] = json.loads(d["badges"]) if d["badges"] else []
    d["niveau"] = get_niveau(d["pts_alltime"])
    return d

def reset_serie(user_id: str):
    with get_conn() as conn:
        conn.execute("UPDATE joueurs SET serie = 0 WHERE user_id = ?", (user_id,))

def reset_streak_for_users(user_ids: set):
    """Remet serie à 0 pour tous les joueurs qui ont raté la partie (n'ont pas gagné)."""
    if not user_ids:
        return
    with get_conn() as conn:
        for uid in user_ids:
            conn.execute("UPDATE joueurs SET serie = 0 WHERE user_id = ?", (uid,))

def add_badge(user_id: str, badge: str):
    add_badges(user_id, [badge])

def add_badges(user_id: str, badges_to_add: list) -> list:
    """Ajoute les badges manquants. Retourne la liste des badges réellement nouveaux."""
    if not badges_to_add:
        return []
    with get_conn() as conn:
        row = conn.execute("SELECT badges FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return []
        existing = json.loads(row["badges"]) if row["badges"] else []
        new = [b for b in badges_to_add if b not in existing]
        if new:
            existing.extend(new)
            conn.execute("UPDATE joueurs SET badges = ? WHERE user_id = ?",
                         (json.dumps(existing), user_id))
    return new

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

def get_classement_victoires(limit: int = 10) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT name, victoires, pts_alltime
            FROM joueurs
            WHERE victoires > 0
            ORDER BY victoires DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [{"name": r["name"], "victoires": r["victoires"], "niveau": get_niveau(r["pts_alltime"])} for r in rows]

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

def retirer_points_joueur(nom: str, montant: int) -> dict:
    """
    Retire `montant` pts (alltime + hebdo) au joueur dont le nom correspond.
    Retourne {"status": "not_found"}, {"status": "multiple", "joueurs": [...]},
    ou {"status": "ok", "name": ..., "avant": ..., "apres": ...}.
    """
    with get_conn() as conn:
        # Essai par user_id exact d'abord, sinon recherche par nom
        rows = conn.execute(
            "SELECT user_id, name, pts_alltime FROM joueurs WHERE user_id = ?", (nom,)
        ).fetchall()
        if not rows:
            rows = conn.execute(
                "SELECT user_id, name, pts_alltime FROM joueurs WHERE name LIKE ? COLLATE NOCASE",
                (f"%{nom}%",)
            ).fetchall()
        if not rows:
            return {"status": "not_found"}
        if len(rows) > 1:
            return {"status": "multiple", "joueurs": [r["name"] for r in rows]}
        row = rows[0]
        nouveaux_pts = max(0, row["pts_alltime"] - montant)
        conn.execute(
            "UPDATE joueurs SET pts_alltime = ?, pts_hebdo = MAX(0, pts_hebdo - ?) WHERE user_id = ?",
            (nouveaux_pts, montant, row["user_id"])
        )
    return {"status": "ok", "name": row["name"], "avant": row["pts_alltime"], "apres": nouveaux_pts}

def utiliser_saboteur(user_id: str, target_nom: str) -> dict:
    """Consomme le badge Saboteur de user_id et retire 20 pts à la cible."""
    with get_conn() as conn:
        row = conn.execute("SELECT badges FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return {"status": "no_badge"}
        badges = json.loads(row["badges"]) if row["badges"] else []
        if "💣 Saboteur" not in badges:
            return {"status": "no_badge"}

        cible_rows = conn.execute(
            "SELECT user_id, name, pts_alltime FROM joueurs WHERE user_id = ?", (target_nom,)
        ).fetchall()
        if not cible_rows:
            cible_rows = conn.execute(
                "SELECT user_id, name, pts_alltime FROM joueurs WHERE name LIKE ? COLLATE NOCASE",
                (f"%{target_nom}%",)
            ).fetchall()
        if not cible_rows:
            return {"status": "target_not_found"}
        if len(cible_rows) > 1:
            return {"status": "multiple", "joueurs": [r["name"] for r in cible_rows]}
        cible = cible_rows[0]
        if cible["user_id"] == user_id:
            return {"status": "self_target"}

        badges.remove("💣 Saboteur")
        conn.execute("UPDATE joueurs SET badges = ? WHERE user_id = ?",
                     (json.dumps(badges), user_id))
        nouveaux_pts = max(0, cible["pts_alltime"] - 20)
        conn.execute(
            "UPDATE joueurs SET pts_alltime = ?, pts_hebdo = MAX(0, pts_hebdo - 20) WHERE user_id = ?",
            (nouveaux_pts, cible["user_id"])
        )
    return {"status": "ok", "target_name": cible["name"],
            "avant": cible["pts_alltime"], "apres": nouveaux_pts}

# ── Chats enregistrés ────────────────────────────────────────────
def save_chat(chat_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO chats_enregistres (chat_id) VALUES (?)", (chat_id,)
        )

def get_all_chats() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT chat_id FROM chats_enregistres").fetchall()
    return [r["chat_id"] for r in rows]

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
