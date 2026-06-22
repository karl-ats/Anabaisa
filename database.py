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
                user_id          TEXT PRIMARY KEY,
                name             TEXT NOT NULL,
                pts_alltime      INTEGER DEFAULT 0,
                pts_hebdo        INTEGER DEFAULT 0,
                victoires        INTEGER DEFAULT 0,
                serie            INTEGER DEFAULT 0,
                badges           TEXT    DEFAULT ''
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
            CREATE INDEX IF NOT EXISTS idx_parties_chat ON parties(chat_id);
        """)
    # Migrations idempotentes
    for col_sql in [
        "ALTER TABLE joueurs ADD COLUMN victoires_hard      INTEGER DEFAULT 0",
        "ALTER TABLE joueurs ADD COLUMN victoires_tournoi   INTEGER DEFAULT 0",
    ]:
        try:
            with get_conn() as conn:
                conn.execute(col_sql)
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

def save_partie(chat_id: int, user_id: str, mot: str, difficulte: str, temps_rep: float):
    """Enregistre une victoire dans l'historique des parties (pour classements par groupe)."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO parties (chat_id, mot, difficulte, gagnant_id, temps_rep)
            VALUES (?, ?, ?, ?, ?)
        """, (str(chat_id), mot, difficulte, user_id, temps_rep))

# ── Streak ───────────────────────────────────────────────────────
def reset_serie(user_id: str):
    with get_conn() as conn:
        conn.execute("UPDATE joueurs SET serie = 0 WHERE user_id = ?", (user_id,))

def _reset_streak_uid(conn, uid: str):
    """Réinitialise la série d'un joueur (avec gestion Renaissance). Connexion fournie."""
    row = conn.execute("SELECT badges FROM joueurs WHERE user_id = ?", (uid,)).fetchone()
    if not row:
        return
    badges = json.loads(row["badges"]) if row["badges"] else []
    if "🔄 Renaissance" in badges:
        badges.remove("🔄 Renaissance")
        conn.execute(
            "UPDATE joueurs SET serie = 1, badges = ? WHERE user_id = ?",
            (json.dumps(badges), uid)
        )
    else:
        conn.execute("UPDATE joueurs SET serie = 0 WHERE user_id = ?", (uid,))

def reset_streak_for_chat_losers(chat_id: int, winner_id: str):
    """Remet la série à 0 pour tous les joueurs actifs du groupe sauf le gagnant.
    Passer winner_id='' pour un timeout où personne n'a gagné."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT gagnant_id FROM parties WHERE chat_id = ? AND gagnant_id IS NOT NULL AND gagnant_id != ?",
            (str(chat_id), winner_id)
        ).fetchall()
        for row in rows:
            _reset_streak_uid(conn, row["gagnant_id"])

# ── Badges permanents ────────────────────────────────────────────
def add_badge(user_id: str, badge: str):
    add_badges(user_id, [badge])

def add_badges(user_id: str, badges_to_add: list) -> list:
    """Ajoute des badges sans doublon (permanents). Retourne les nouveaux."""
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

# ── Badges consommables (stackables) ─────────────────────────────
def add_consumable_badge(user_id: str, badge: str):
    """Ajoute un badge même s'il existe déjà (badges consommables/stackables)."""
    with get_conn() as conn:
        row = conn.execute("SELECT badges FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return
        badges = json.loads(row["badges"]) if row["badges"] else []
        badges.append(badge)
        conn.execute("UPDATE joueurs SET badges = ? WHERE user_id = ?",
                     (json.dumps(badges), user_id))

def remove_badge(user_id: str, badge: str) -> bool:
    """Retire une occurrence du badge. Retourne True si consommé."""
    with get_conn() as conn:
        row = conn.execute("SELECT badges FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return False
        badges = json.loads(row["badges"]) if row["badges"] else []
        if badge not in badges:
            return False
        badges.remove(badge)
        conn.execute("UPDATE joueurs SET badges = ? WHERE user_id = ?",
                     (json.dumps(badges), user_id))
    return True

def has_badge(user_id: str, badge: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT badges FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return False
    badges = json.loads(row["badges"]) if row["badges"] else []
    return badge in badges

# ── Actions consommables ─────────────────────────────────────────
def utiliser_saboteur(user_id: str, target_nom: str) -> dict:
    """Consomme Saboteur et retire 20 pts à la cible (bloqué si Bouclier)."""
    with get_conn() as conn:
        row = conn.execute("SELECT badges FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return {"status": "no_badge"}
        badges = json.loads(row["badges"]) if row["badges"] else []
        if "💣 Saboteur" not in badges:
            return {"status": "no_badge"}

        cible_rows = conn.execute(
            "SELECT user_id, name, pts_alltime, badges FROM joueurs WHERE user_id = ?", (target_nom,)
        ).fetchall()
        if not cible_rows:
            cible_rows = conn.execute(
                "SELECT user_id, name, pts_alltime, badges FROM joueurs WHERE name LIKE ? COLLATE NOCASE",
                (f"%{target_nom}%",)
            ).fetchall()
        if not cible_rows:
            return {"status": "target_not_found"}
        if len(cible_rows) > 1:
            return {"status": "multiple", "joueurs": [r["name"] for r in cible_rows]}
        cible = cible_rows[0]
        if cible["user_id"] == user_id:
            return {"status": "self_target"}

        # Consomme le Saboteur de l'attaquant dans tous les cas
        badges.remove("💣 Saboteur")
        conn.execute("UPDATE joueurs SET badges = ? WHERE user_id = ?",
                     (json.dumps(badges), user_id))

        # Vérifie si la cible a un Bouclier
        cible_badges = json.loads(cible["badges"]) if cible["badges"] else []
        if "🛡️ Bouclier" in cible_badges:
            cible_badges.remove("🛡️ Bouclier")
            conn.execute("UPDATE joueurs SET badges = ? WHERE user_id = ?",
                         (json.dumps(cible_badges), cible["user_id"]))
            return {"status": "blocked", "target_name": cible["name"]}

        nouveaux_pts = max(0, cible["pts_alltime"] - 20)
        conn.execute(
            "UPDATE joueurs SET pts_alltime = ?, pts_hebdo = MAX(0, pts_hebdo - 20) WHERE user_id = ?",
            (nouveaux_pts, cible["user_id"])
        )
    return {"status": "ok", "target_name": cible["name"],
            "avant": cible["pts_alltime"], "apres": nouveaux_pts}

def utiliser_prestige(user_id: str, target_nom: str) -> dict:
    """Consomme Prestige et transfère 30 pts de l'utilisateur vers la cible."""
    with get_conn() as conn:
        row = conn.execute("SELECT badges, pts_alltime FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return {"status": "no_badge"}
        badges = json.loads(row["badges"]) if row["badges"] else []
        if "👑 Prestige" not in badges:
            return {"status": "no_badge"}

        cible_rows = conn.execute(
            "SELECT user_id, name FROM joueurs WHERE user_id = ?", (target_nom,)
        ).fetchall()
        if not cible_rows:
            cible_rows = conn.execute(
                "SELECT user_id, name FROM joueurs WHERE name LIKE ? COLLATE NOCASE",
                (f"%{target_nom}%",)
            ).fetchall()
        if not cible_rows:
            return {"status": "target_not_found"}
        if len(cible_rows) > 1:
            return {"status": "multiple", "joueurs": [r["name"] for r in cible_rows]}
        cible = cible_rows[0]
        if cible["user_id"] == user_id:
            return {"status": "self_target"}

        badges.remove("👑 Prestige")
        conn.execute("UPDATE joueurs SET badges = ? WHERE user_id = ?",
                     (json.dumps(badges), user_id))
        conn.execute(
            "UPDATE joueurs SET pts_alltime = MAX(0, pts_alltime - 30), pts_hebdo = MAX(0, pts_hebdo - 30) WHERE user_id = ?",
            (user_id,)
        )
        conn.execute(
            "UPDATE joueurs SET pts_alltime = pts_alltime + 30, pts_hebdo = pts_hebdo + 30 WHERE user_id = ?",
            (cible["user_id"],)
        )
    return {"status": "ok", "target_name": cible["name"]}

def add_victoire_tournoi(user_id: str):
    """Incrémente victoires_tournoi et octroie un badge Prolongation."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE joueurs SET victoires_tournoi = victoires_tournoi + 1 WHERE user_id = ?",
            (user_id,)
        )
    add_consumable_badge(user_id, "⏱️ Prolongation")

# ── Classements par groupe (per-chat) ───────────────────────────
def _joueurs_du_chat(conn, chat_id: int) -> set:
    """Retourne les user_ids ayant joué dans ce chat."""
    rows = conn.execute(
        "SELECT DISTINCT gagnant_id FROM parties WHERE chat_id = ? AND gagnant_id IS NOT NULL",
        (str(chat_id),)
    ).fetchall()
    return {r["gagnant_id"] for r in rows}

def get_topscore(chat_id: int, user_id: str, limit: int = 10) -> tuple:
    """Classement all-time par points dans ce groupe + rang personnel."""
    with get_conn() as conn:
        joueurs_chat = _joueurs_du_chat(conn, chat_id)
        if not joueurs_chat:
            # Fallback : classement global si aucun historique de parties
            rows = conn.execute(
                "SELECT name, pts_alltime AS points FROM joueurs WHERE pts_alltime > 0 ORDER BY pts_alltime DESC LIMIT ?",
                (limit,)
            ).fetchall()
        else:
            placeholders = ",".join("?" * len(joueurs_chat))
            rows = conn.execute(
                f"SELECT name, pts_alltime AS points FROM joueurs WHERE user_id IN ({placeholders}) AND pts_alltime > 0 ORDER BY pts_alltime DESC LIMIT ?",
                (*joueurs_chat, limit)
            ).fetchall()

        my_row = conn.execute("SELECT pts_alltime FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
        my_pts = my_row["pts_alltime"] if my_row else 0

        if joueurs_chat and user_id in joueurs_chat:
            rank_row = conn.execute(
                f"SELECT COUNT(*) + 1 AS rang FROM joueurs WHERE user_id IN ({placeholders}) AND pts_alltime > ?",
                (*joueurs_chat, my_pts)
            ).fetchone()
            rang = rank_row["rang"] if rank_row else None
        elif not joueurs_chat:
            rank_row = conn.execute(
                "SELECT COUNT(*) + 1 AS rang FROM joueurs WHERE pts_alltime > ? AND pts_alltime > 0",
                (my_pts,)
            ).fetchone()
            rang = rank_row["rang"] if rank_row else None
        else:
            rang = None

    classement = [{"name": r["name"], "points": r["points"], "niveau": get_niveau(r["points"])} for r in rows]
    return classement, rang, my_pts

def get_topwin(chat_id: int, user_id: str, limit: int = 10) -> tuple:
    """Classement all-time par victoires dans ce groupe + rang personnel."""
    with get_conn() as conn:
        joueurs_chat = _joueurs_du_chat(conn, chat_id)
        if not joueurs_chat:
            rows = conn.execute(
                "SELECT name, victoires, pts_alltime FROM joueurs WHERE victoires > 0 ORDER BY victoires DESC LIMIT ?",
                (limit,)
            ).fetchall()
        else:
            placeholders = ",".join("?" * len(joueurs_chat))
            rows = conn.execute(
                f"SELECT name, victoires, pts_alltime FROM joueurs WHERE user_id IN ({placeholders}) AND victoires > 0 ORDER BY victoires DESC LIMIT ?",
                (*joueurs_chat, limit)
            ).fetchall()

        my_row = conn.execute("SELECT victoires FROM joueurs WHERE user_id = ?", (user_id,)).fetchone()
        my_vic = my_row["victoires"] if my_row else 0

        if joueurs_chat and user_id in joueurs_chat:
            rank_row = conn.execute(
                f"SELECT COUNT(*) + 1 AS rang FROM joueurs WHERE user_id IN ({placeholders}) AND victoires > ?",
                (*joueurs_chat, my_vic)
            ).fetchone()
            rang = rank_row["rang"] if rank_row else None
        elif not joueurs_chat:
            rank_row = conn.execute(
                "SELECT COUNT(*) + 1 AS rang FROM joueurs WHERE victoires > ? AND victoires > 0",
                (my_vic,)
            ).fetchone()
            rang = rank_row["rang"] if rank_row else None
        else:
            rang = None

    classement = [{"name": r["name"], "victoires": r["victoires"], "niveau": get_niveau(r["pts_alltime"])} for r in rows]
    return classement, rang, my_vic

# ── Classement hebdo (usage interne) ────────────────────────────
def get_champion_semaine() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT user_id, name, pts_hebdo FROM joueurs
            WHERE pts_hebdo > 0
            ORDER BY pts_hebdo DESC LIMIT 1
        """).fetchone()
    return {"user_id": row["user_id"], "name": row["name"], "pts": row["pts_hebdo"]} if row else None

def reset_hebdo():
    with get_conn() as conn:
        conn.execute("UPDATE joueurs SET pts_hebdo = 0")
        conn.execute("UPDATE hebdo_reset SET last_reset = CURRENT_TIMESTAMP WHERE id = 1")

# ── Admin ────────────────────────────────────────────────────────
def retirer_points_joueur(nom: str, montant: int) -> dict:
    with get_conn() as conn:
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
