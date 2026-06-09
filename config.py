import os

# ── Telegram ────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "METS_TON_TOKEN_ICI")

# ── Base de données ─────────────────────────────────────────────
DB_PATH = os.environ.get("DB_PATH", "anagram.db")

# ── Fuseau horaire ──────────────────────────────────────────────
TIMEZONE = "Africa/Douala"   # UTC+1 Yaoundé

# ── Timings partie rapide (secondes) ───────────────────────────
DELAY_TAUNT   = 8    # relance taquine
DELAY_HINT    = 10   # indice automatique
DELAY_SOLUTION = 30  # solution automatique

# ── Tournoi ─────────────────────────────────────────────────────
TOURNAMENT_ROUNDS = 5

# ── Points par difficulté ───────────────────────────────────────
POINTS = {"easy": 1, "medium": 2, "hard": 3}
BONUS_SPEED_SECONDS = 5   # si trouvé en moins de X secondes → +1 pt

# ── Niveaux joueur ──────────────────────────────────────────────
LEVELS = [
    (0,  "🐣 Débutant"),
    (10, "📚 Amateur"),
    (30, "🧠 Expert"),
    (75, "👑 Maître des mots"),
]

# ── Défi du jour ────────────────────────────────────────────────
DAILY_HOUR   = 9    # heure d'envoi (UTC+1)
DAILY_MINUTE = 0
RESULT_HOUR  = 21   # heure annonce vainqueur du jour
RESULT_MINUTE = 0
