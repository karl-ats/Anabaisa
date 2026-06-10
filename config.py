import os

# ── Telegram ────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "METS_TON_TOKEN_ICI")

# ── Base de données ─────────────────────────────────────────────
DB_PATH = os.environ.get("DB_PATH", "anagram.db")

# ── Fuseau horaire ──────────────────────────────────────────────
TIMEZONE = "Africa/Douala"   # UTC+1 Yaoundé

# ── Timings par difficulté (secondes) ───────────────────────────
DELAY_TAUNT = 8   # relance taquine (toutes difficultés)

# Indices automatiques : liste des délais par difficulté
HINT_SCHEDULE = {
    "easy":   [15],           # 1 indice max à 15s
    "medium": [12, 35],       # 2 indices : 12s puis 35s
    "hard":   [12, 30, 55],   # 3 indices : 12s, 30s, 55s
}

# Délai avant révélation automatique de la solution
SOLUTION_DELAY = {
    "easy":   45,
    "medium": 80,
    "hard":   120,
}

def hint_timing_str(difficulte: str) -> str:
    """Retourne la chaîne de timing affichée sous l'anagramme."""
    first = HINT_SCHEDULE.get(difficulte, [15])[0]
    sol   = SOLUTION_DELAY.get(difficulte, 60)
    n     = len(HINT_SCHEDULE.get(difficulte, [15]))
    return f"Premier indice dans {first}s · Solution dans {sol}s · {n} indice{'s' if n > 1 else ''} max"

# ── Tournoi ─────────────────────────────────────────────────────
TOURNAMENT_ROUNDS = 5

# ── Points par difficulté ───────────────────────────────────────
POINTS = {"easy": 1, "medium": 2, "hard": 3}
BONUS_SPEED_SECONDS = 5   # si trouvé en moins de X secondes → +1 pt

# ── Niveaux joueur ──────────────────────────────────────────────
LEVELS = [
    (0,   "🐣 Débutant"),
    (15,  "📖 Apprenti"),
    (35,  "🔤 Initié"),
    (65,  "🧩 Confirmé"),
    (110, "🧠 Expert"),
    (175, "⚡ Virtuose"),
    (275, "🎯 Maître"),
    (400, "🏆 Grand Maître"),
    (600, "👑 Légende des mots"),
]

# ── Défi du jour ────────────────────────────────────────────────
DAILY_HOUR   = 9    # heure d'envoi (UTC+1)
DAILY_MINUTE = 0
RESULT_HOUR  = 21   # heure annonce vainqueur du jour
RESULT_MINUTE = 0
