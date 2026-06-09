import asyncio
import random
import time
from datetime import datetime, timezone

from config import (
    DELAY_TAUNT, DELAY_HINT, DELAY_SOLUTION,
    TOURNAMENT_ROUNDS, POINTS, BONUS_SPEED_SECONDS
)
import database as db
import messages as msg
from words import get_word

# ── Utilitaires ─────────────────────────────────────────────────
def melanger(mot: str) -> str:
    lettres = list(mot)
    for _ in range(100):
        random.shuffle(lettres)
        if "".join(lettres) != mot:
            return "".join(lettres)
    return "".join(reversed(mot))

def masque_indice(mot: str) -> str:
    if len(mot) <= 2:
        return mot
    milieu = "_ " * (len(mot) - 2)
    return f"{mot[0]} {milieu}{mot[-1]}"

def nettoyer(texte: str) -> str:
    """Normalise accents et casse pour la comparaison."""
    import unicodedata
    texte = texte.strip().lower()
    return unicodedata.normalize("NFD", texte).encode("ascii", "ignore").decode()

# ── État global ──────────────────────────────────────────────────
# Structure par chat_id :
# {
#   "mode":        "quick" | "tournament" | "daily",
#   "difficulte":  "easy" | "medium" | "hard",
#   "mot":         str,
#   "anagramme":   str,
#   "actif":       bool,
#   "start_time":  float,
#   "tasks":       [asyncio.Task, ...],
#   # Tournoi uniquement :
#   "manche":      int,
#   "scores_tournoi": {user_id: {"name": str, "pts": int}},
# }
GAMES: dict = {}

async def _cancel_tasks(chat_id: int):
    for t in GAMES.get(chat_id, {}).get("tasks", []):
        if not t.done():
            t.cancel()

# ── Lancement partie ─────────────────────────────────────────────
async def start_round(
    chat_id: int,
    difficulte: str,
    bot,
    mode: str = "quick",
    manche: int = 1,
    scores_tournoi: dict = None,
):
    mot      = get_word(difficulte)
    anag     = melanger(mot)
    loop     = asyncio.get_event_loop()

    await _cancel_tasks(chat_id)

    GAMES[chat_id] = {
        "mode":           mode,
        "difficulte":     difficulte,
        "mot":            mot,
        "anagramme":      anag,
        "actif":          True,
        "start_time":     time.time(),
        "tasks":          [],
        "manche":         manche,
        "scores_tournoi": scores_tournoi or {},
    }

    # Tâches automatiques
    t1 = loop.create_task(_taunt_task(chat_id, bot))
    t2 = loop.create_task(_hint_task(chat_id, bot))
    t3 = loop.create_task(_solution_task(chat_id, bot))
    GAMES[chat_id]["tasks"] = [t1, t2, t3]

    return mot, anag

# ── Tâches chronométrées ─────────────────────────────────────────
async def _taunt_task(chat_id: int, bot):
    await asyncio.sleep(DELAY_TAUNT)
    if GAMES.get(chat_id, {}).get("actif"):
        await bot.send_message(chat_id, msg.msg_relance(), parse_mode="Markdown")

async def _hint_task(chat_id: int, bot):
    await asyncio.sleep(DELAY_HINT)
    if GAMES.get(chat_id, {}).get("actif"):
        mot = GAMES[chat_id]["mot"]
        await bot.send_message(
            chat_id,
            msg.msg_indice(masque_indice(mot), len(mot)),
            parse_mode="Markdown"
        )

async def _solution_task(chat_id: int, bot):
    await asyncio.sleep(DELAY_SOLUTION)
    game = GAMES.get(chat_id, {})
    if not game.get("actif"):
        return
    mot  = game["mot"]
    mode = game["mode"]
    GAMES[chat_id]["actif"] = False

    await bot.send_message(chat_id, msg.msg_solution(mot, "timeout"), parse_mode="Markdown")

    if mode == "tournament":
        await _next_manche_or_end(chat_id, bot)

# ── Vérification réponse ─────────────────────────────────────────
async def check_answer(chat_id: int, user_id: str, user_name: str, texte: str, bot) -> bool:
    game = GAMES.get(chat_id)
    if not game or not game["actif"]:
        return False

    mot = game["mot"]
    if nettoyer(texte) != nettoyer(mot):
        return False

    # Bonne réponse !
    game["actif"] = False
    await _cancel_tasks(chat_id)

    elapsed     = time.time() - game["start_time"]
    difficulte  = game["difficulte"]
    pts_base    = POINTS[difficulte]
    bonus       = elapsed < BONUS_SPEED_SECONDS
    pts_total   = pts_base + (1 if bonus else 0)

    stats = db.add_points(user_id, user_name, pts_total)

    # Badges
    if stats["serie"] >= 5:
        db.add_badge(user_id, "⚡ Foudre de guerre")
    hour = datetime.now(timezone.utc).hour + 1  # UTC+1
    if 0 <= hour < 5:
        db.add_badge(user_id, "🌙 Noctambule")
    if elapsed < DELAY_HINT:
        db.add_badge(user_id, "🎯 Sans indice")

    await bot.send_message(
        chat_id,
        msg.msg_victoire(user_name, mot, elapsed, pts_total, stats["pts_alltime"], stats["niveau"], bonus),
        parse_mode="Markdown"
    )

    # Tournoi : mettre à jour scores
    if game["mode"] == "tournament":
        st = game["scores_tournoi"]
        if user_id not in st:
            st[user_id] = {"name": user_name, "pts": 0}
        st[user_id]["pts"] += pts_total
        await _next_manche_or_end(chat_id, bot)

    # Défi du jour
    if game["mode"] == "daily":
        from datetime import date
        today = date.today().isoformat()
        db.set_defi_gagnant(today, user_id, pts_total)

    return True

# ── Tournoi ──────────────────────────────────────────────────────
async def start_tournament(chat_id: int, difficulte: str, bot):
    await bot.send_message(
        chat_id,
        msg.msg_debut_tournoi(difficulte, TOURNAMENT_ROUNDS),
        parse_mode="Markdown"
    )
    await asyncio.sleep(3)
    await _launch_manche(chat_id, difficulte, bot, manche=1, scores_tournoi={})

async def _launch_manche(chat_id: int, difficulte: str, bot, manche: int, scores_tournoi: dict):
    mot, anag = await start_round(chat_id, difficulte, bot, mode="tournament",
                                  manche=manche, scores_tournoi=scores_tournoi)
    await bot.send_message(
        chat_id,
        msg.msg_manche(manche, TOURNAMENT_ROUNDS, anag, difficulte, len(mot)),
        parse_mode="Markdown"
    )

async def _next_manche_or_end(chat_id: int, bot):
    game      = GAMES.get(chat_id, {})
    manche    = game.get("manche", 1)
    difficulte = game.get("difficulte", "easy")
    scores    = game.get("scores_tournoi", {})

    if manche >= TOURNAMENT_ROUNDS:
        await asyncio.sleep(2)
        await bot.send_message(chat_id, msg.msg_fin_tournoi(scores), parse_mode="Markdown")
        GAMES.pop(chat_id, None)
    else:
        await asyncio.sleep(3)
        await _launch_manche(chat_id, difficulte, bot, manche + 1, scores)

# ── Stop ─────────────────────────────────────────────────────────
async def stop_game(chat_id: int) -> str | None:
    game = GAMES.get(chat_id)
    if not game or not game["actif"]:
        return None
    mot = game["mot"]
    game["actif"] = False
    await _cancel_tasks(chat_id)
    GAMES.pop(chat_id, None)
    return mot
