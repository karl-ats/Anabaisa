import asyncio
import random
import time
import unicodedata
from datetime import datetime

import pytz

from config import (
    DELAY_TAUNT, HINT_SCHEDULE, SOLUTION_DELAY,
    TOURNAMENT_ROUNDS, POINTS, BONUS_SPEED_SECONDS, TIMEZONE
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

MAX_HINTS = {"easy": 1, "medium": 2, "hard": 3}

def masque_indice(mot: str, revealed: set) -> str:
    """Construit le masque d'indice selon les positions révélées."""
    return " ".join(mot[i] if i in revealed else "_" for i in range(len(mot)))

def _init_revealed(mot: str) -> set:
    """Premier indice : première et dernière lettre."""
    if len(mot) <= 2:
        return set(range(len(mot)))
    return {0, len(mot) - 1}

def _next_revealed(mot: str, current: set) -> set:
    """Ajoute 1-2 lettres aléatoires du milieu non encore révélées."""
    middle = [i for i in range(1, len(mot) - 1) if i not in current]
    if not middle:
        return current
    count = min(2, len(middle))
    return current | set(random.sample(middle, count))

def give_hint(chat_id: int):
    """Avance d'un cran l'indice et retourne (masque, hint_count, max_hints) ou None si max atteint."""
    game = GAMES.get(chat_id)
    if not game or not game.get("actif"):
        return None
    diff    = game["difficulte"]
    max_h   = MAX_HINTS.get(diff, 1)
    count   = game["hint_count"]
    if count >= max_h:
        return None
    mot      = game["mot"]
    revealed = game["revealed_positions"]
    revealed = _init_revealed(mot) if count == 0 else _next_revealed(mot, revealed)
    game["revealed_positions"] = revealed
    game["hint_count"] = count + 1
    return masque_indice(mot, revealed), count + 1, max_h

def nettoyer(texte: str) -> str:
    """Normalise accents et casse pour la comparaison."""
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
    mot: str = None,
):
    if mot is None:
        mot = get_word(difficulte)
    anag = melanger(mot)

    await _cancel_tasks(chat_id)

    GAMES[chat_id] = {
        "mode":              mode,
        "difficulte":        difficulte,
        "mot":               mot,
        "anagramme":         anag,
        "actif":             True,
        "start_time":        None,   # défini dans start_tasks, après envoi du message
        "tasks":             [],
        "manche":            manche,
        "scores_tournoi":    scores_tournoi or {},
        "hint_count":        0,
        "revealed_positions": set(),
    }

    return mot, anag

def start_tasks(chat_id: int, bot):
    """Démarre les timers APRÈS que le message initial a été envoyé avec succès."""
    game = GAMES.get(chat_id)
    if not game:
        return
    game["start_time"] = time.time()
    diff = game["difficulte"]
    sol_delay   = SOLUTION_DELAY.get(diff, 60)
    hint_delays = HINT_SCHEDULE.get(diff, [15])
    loop = asyncio.get_running_loop()
    tasks = [loop.create_task(_taunt_task(chat_id, bot))]
    for delay in hint_delays:
        tasks.append(loop.create_task(_hint_task(chat_id, bot, delay)))
    tasks.append(loop.create_task(_solution_task(chat_id, bot, sol_delay)))
    game["tasks"] = tasks

# ── Tâches chronométrées ─────────────────────────────────────────
async def _taunt_task(chat_id: int, bot):
    await asyncio.sleep(DELAY_TAUNT)
    if GAMES.get(chat_id, {}).get("actif"):
        await bot.send_message(chat_id, msg.msg_relance(), parse_mode="Markdown")

async def _hint_task(chat_id: int, bot, delay: int = 15):
    await asyncio.sleep(delay)
    if not GAMES.get(chat_id, {}).get("actif"):
        return
    result = give_hint(chat_id)
    if result:
        masque, count, max_h = result
        mot = GAMES[chat_id]["mot"]
        await bot.send_message(
            chat_id,
            msg.msg_indice(masque, len(mot), count, max_h),
            parse_mode="Markdown"
        )

async def _solution_task(chat_id: int, bot, delay: int = 60):
    await asyncio.sleep(delay)
    game = GAMES.get(chat_id, {})
    if not game.get("actif"):
        return
    mot  = game["mot"]
    mode = game["mode"]
    GAMES[chat_id]["actif"] = False

    # Annuler les AUTRES tâches (taunt/hint) — ne pas s'annuler soi-même
    current = asyncio.current_task()
    for t in game.get("tasks", []):
        if not t.done() and t is not current:
            t.cancel()

    await bot.send_message(chat_id, msg.msg_solution(mot, "timeout", mode), parse_mode="Markdown")

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
    tz = pytz.timezone(TIMEZONE)
    hour = datetime.now(tz).hour
    if 0 <= hour < 5:
        db.add_badge(user_id, "🌙 Noctambule")
    first_hint_delay = HINT_SCHEDULE.get(difficulte, [15])[0]
    if elapsed < first_hint_delay:
        db.add_badge(user_id, "🎯 Sans indice")

    await bot.send_message(
        chat_id,
        msg.msg_victoire(user_name, mot, elapsed, pts_total, stats["pts_alltime"], stats["niveau"], bonus, game["mode"]),
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
    start_tasks(chat_id, bot)

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
async def stop_game(chat_id: int) -> dict | None:
    """Retourne un dict avec mot, was_active, mode, scores_tournoi — ou None si aucune partie."""
    game = GAMES.get(chat_id)
    if not game:
        return None
    result = {
        "mot":            game["mot"],
        "was_active":     game["actif"],
        "mode":           game["mode"],
        "scores_tournoi": dict(game.get("scores_tournoi", {})),
    }
    game["actif"] = False
    await _cancel_tasks(chat_id)
    GAMES.pop(chat_id, None)
    return result
