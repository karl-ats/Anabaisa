import asyncio
import random
import time
import unicodedata
from datetime import datetime, date

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
    return " ".join(mot[i] if i in revealed else "_" for i in range(len(mot)))

def _init_revealed(mot: str) -> set:
    if len(mot) <= 2:
        return set(range(len(mot)))
    return {0, len(mot) - 1}

def _next_revealed(mot: str, current: set) -> set:
    middle = [i for i in range(1, len(mot) - 1) if i not in current]
    if not middle:
        return current
    count = min(2, len(middle))
    return current | set(random.sample(middle, count))

def give_hint(chat_id: int):
    """Retourne (masque, hint_count, max_hints) ou None si max atteint."""
    game = GAMES.get(chat_id)
    if not game or not game.get("actif"):
        return None
    diff     = game["difficulte"]
    max_h    = MAX_HINTS.get(diff, 1)
    count    = game["hint_count"]
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
GAMES: dict = {}
ARENAS: dict = {}
# Structure ARENAS[chat_id] :
# {
#   "difficulte": str, "mise": int,
#   "organisateur_id": str, "phase": "lobby"|"manche"|"duel"|"termine",
#   "joueurs": {user_id: {"name": str, "pts": int}},
#   "elimines": [(user_id, name)],   # du premier éliminé au finaliste
#   "manche": int, "duel_mode": bool, "duel_joueurs": set,
#   "pot": int, "lobby_task": Task|None,
# }

def _cancel_tasks_sync(chat_id: int):
    game = GAMES.get(chat_id, {})
    for t in game.get("hint_tasks", []) + game.get("tasks", []):
        if not t.done():
            t.cancel()
    sol = game.get("solution_task")
    if sol and not sol.done():
        sol.cancel()

async def _cancel_tasks(chat_id: int):
    _cancel_tasks_sync(chat_id)

def cancel_hint_tasks(chat_id: int):
    """Annule uniquement les tâches d'indice auto (appelé par /indice manuel)."""
    game = GAMES.get(chat_id, {})
    for t in game.get("hint_tasks", []):
        if not t.done():
            t.cancel()
    game["hint_tasks"] = []

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
        "mode":               mode,
        "difficulte":         difficulte,
        "mot":                mot,
        "anagramme":          anag,
        "actif":              True,
        "start_time":         None,
        "tasks":              [],      # taunt task
        "hint_tasks":         [],      # hint tasks (annulables séparément)
        "solution_task":      None,
        "manche":             manche,
        "scores_tournoi":     scores_tournoi or {},
        "hint_count":         0,
        "revealed_positions": set(),
        "guessed_users":      set(),
    }

    return mot, anag

def start_tasks(chat_id: int, bot):
    """Démarre les timers APRÈS que le message initial a été envoyé."""
    game = GAMES.get(chat_id)
    if not game:
        return
    game["start_time"] = time.time()
    diff        = game["difficulte"]
    sol_delay   = SOLUTION_DELAY.get(diff, 60)
    hint_delays = HINT_SCHEDULE.get(diff, [15])
    loop = asyncio.get_running_loop()

    game["tasks"] = [loop.create_task(_taunt_task(chat_id, bot))]
    game["hint_tasks"] = [loop.create_task(_hint_task(chat_id, bot, d)) for d in hint_delays]
    game["solution_task"] = loop.create_task(_solution_task(chat_id, bot, sol_delay))

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

    current = asyncio.current_task()
    for t in game.get("tasks", []) + game.get("hint_tasks", []):
        if not t.done() and t is not current:
            t.cancel()

    if mode == "arena":
        await bot.send_message(
            chat_id,
            f"⏰ *Temps écoulé !* Personne n'a trouvé... Le mot était *{mot.upper()}*",
            parse_mode="Markdown"
        )
        await _arena_after_round(chat_id, bot, winner_id=None)
        return

    await bot.send_message(chat_id, msg.msg_solution(mot, "timeout", mode), parse_mode="Markdown")
    db.reset_streak_for_chat_losers(chat_id, "")

    if mode == "tournament":
        await _next_manche_or_end(chat_id, bot)
    else:
        GAMES.pop(chat_id, None)

# ── Extension de temps (badge Prolongation) ──────────────────────
async def extend_game(chat_id: int, seconds: int, bot):
    """Prolonge la partie en cours de `seconds` secondes."""
    game = GAMES.get(chat_id)
    if not game or not game.get("actif"):
        return False

    # Annule l'ancien task solution
    old_sol = game.get("solution_task")
    if old_sol and not old_sol.done():
        old_sol.cancel()

    # Calcule le délai restant + extension
    diff = game["difficulte"]
    elapsed = time.time() - (game["start_time"] or time.time())
    original_delay = SOLUTION_DELAY.get(diff, 60)
    remaining = max(5, original_delay - elapsed + seconds)

    loop = asyncio.get_running_loop()
    game["solution_task"] = loop.create_task(_solution_task(chat_id, bot, remaining))
    return True

# ── Vérification réponse ─────────────────────────────────────────
async def check_answer(chat_id: int, user_id: str, user_name: str, texte: str, bot) -> bool:
    game = GAMES.get(chat_id)
    if not game or not game["actif"]:
        return False

    if game["start_time"] is None:
        return False

    mot = game["mot"]
    if nettoyer(texte) != nettoyer(mot):
        game["guessed_users"].add(user_id)
        return False

    # Bonne réponse !
    game["actif"] = False
    _cancel_tasks_sync(chat_id)

    elapsed    = time.time() - game["start_time"]
    difficulte = game["difficulte"]
    pts_base   = POINTS[difficulte]
    bonus      = elapsed < BONUS_SPEED_SECONDS
    pts_total  = pts_base + (1 if bonus else 0)

    # Badge Doubleur passif : double les pts si actif
    if db.has_badge(user_id, "💥 Doubleur"):
        pts_total *= 2
        db.remove_badge(user_id, "💥 Doubleur")

    stats      = db.add_points(user_id, user_name, pts_total, difficulte)
    old_niveau = db.get_niveau(stats["pts_alltime"] - pts_total)
    level_up   = old_niveau != stats["niveau"]

    # Enregistre la partie pour les classements par groupe
    db.save_partie(chat_id, user_id, mot, difficulte, elapsed)

    # Reset streak de tous les joueurs actifs du groupe sauf le gagnant
    db.reset_streak_for_chat_losers(chat_id, user_id)

    # ── Badges permanents ──────────────────────────────────────────
    earned_badges = []
    if stats["victoires"] == 1:
        earned_badges.append("🏅 Premier sang")
    if elapsed < 3:
        earned_badges.append("💨 Supersonique")
    if stats["serie"] == 3:
        earned_badges.append("🔥 Enflammé")
    if stats["serie"] >= 5:
        earned_badges.append("⚡ Foudre de guerre")
    if stats["victoires"] == 50:
        earned_badges.append("🧙 Vétéran")
    if stats["victoires_hard"] == 10:
        earned_badges.append("🔤 Lexicomane")
    tz   = pytz.timezone(TIMEZONE)
    hour = datetime.now(tz).hour
    if 0 <= hour < 5:
        earned_badges.append("🌙 Noctambule")
    first_hint_delay = HINT_SCHEDULE.get(difficulte, [15])[0]
    if elapsed < first_hint_delay:
        earned_badges.append("🎯 Sans indice")
    newly_earned = db.add_badges(user_id, earned_badges)

    # ── Badges consommables ────────────────────────────────────────
    if stats["serie"] == 7:
        db.add_consumable_badge(user_id, "💥 Doubleur")
        newly_earned.append("💥 Doubleur")
    if stats["serie"] == 15:
        db.add_consumable_badge(user_id, "🔄 Renaissance")
        newly_earned.append("🔄 Renaissance")
    if stats["victoires"] > 0 and stats["victoires"] % 25 == 0:
        db.add_consumable_badge(user_id, "🛡️ Bouclier")
        newly_earned.append("🛡️ Bouclier")
    # Saboteur (à la 10e victoire d'affilée) — déjà consommable, on le traite ici
    if stats["serie"] == 10:
        db.add_consumable_badge(user_id, "💣 Saboteur")
        newly_earned.append("💣 Saboteur")

    await bot.send_message(
        chat_id,
        msg.msg_victoire(user_name, mot, elapsed, pts_total, stats["pts_alltime"], stats["niveau"], bonus, game["mode"]),
        parse_mode="Markdown"
    )

    if newly_earned:
        await bot.send_message(
            chat_id,
            msg.msg_nouveaux_badges(user_name, newly_earned),
            parse_mode="Markdown"
        )

    if level_up:
        await bot.send_message(
            chat_id,
            msg.msg_level_up(user_name, stats["niveau"]),
            parse_mode="Markdown"
        )

    # Tournoi : mettre à jour scores
    if game["mode"] == "tournament":
        st = game["scores_tournoi"]
        if user_id not in st:
            st[user_id] = {"name": user_name, "pts": 0}
        st[user_id]["pts"] += pts_total
        await _next_manche_or_end(chat_id, bot)
    else:
        if game["mode"] == "daily":
            db.set_defi_gagnant(date.today().isoformat(), user_id, pts_total)
        GAMES.pop(chat_id, None)

    return True

# ── Tournoi ──────────────────────────────────────────────────────
async def start_tournament(chat_id: int, difficulte: str, bot):
    await bot.send_message(
        chat_id,
        msg.msg_debut_tournoi(difficulte, TOURNAMENT_ROUNDS),
        parse_mode="Markdown"
    )
    await asyncio.sleep(3)
    if GAMES.get(chat_id, {}).get("actif"):
        return
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
    game       = GAMES.get(chat_id, {})
    manche     = game.get("manche", 1)
    difficulte = game.get("difficulte", "easy")
    scores     = game.get("scores_tournoi", {})

    if manche >= TOURNAMENT_ROUNDS:
        await asyncio.sleep(2)
        if chat_id not in GAMES:
            return
        await bot.send_message(chat_id, msg.msg_fin_tournoi(scores), parse_mode="Markdown")
        # Récompense le vainqueur du tournoi
        if scores:
            winner_id = max(scores, key=lambda uid: scores[uid]["pts"])
            db.add_victoire_tournoi(winner_id)
        GAMES.pop(chat_id, None)
    else:
        await asyncio.sleep(3)
        if chat_id not in GAMES:
            return
        await _launch_manche(chat_id, difficulte, bot, manche + 1, scores)

# ── Arène ────────────────────────────────────────────────────────
async def start_arena(chat_id: int, difficulte: str, mise: int, org_id: str, org_name: str, bot) -> str:
    if GAMES.get(chat_id, {}).get("actif"):
        return "already_active"
    if ARENAS.get(chat_id, {}).get("phase") in ("lobby", "manche", "duel"):
        return "already_active"
    if mise > 0 and not db.ajuster_pts_brut(org_id, -mise):
        return "no_pts"
    ARENAS[chat_id] = {
        "difficulte": difficulte, "mise": mise,
        "organisateur_id": org_id, "phase": "lobby",
        "joueurs": {org_id: {"name": org_name, "pts": 0}},
        "elimines": [], "manche": 0,
        "manche_phase": 0, "manche_phase_max": 5,
        "duel_mode": False, "duel_joueurs": set(),
        "pot": mise, "lobby_task": None,
    }
    loop = asyncio.get_running_loop()
    ARENAS[chat_id]["lobby_task"] = loop.create_task(_arena_lobby_task(chat_id, bot))
    return "ok"

async def join_arena(chat_id: int, user_id: str, name: str) -> str:
    arena = ARENAS.get(chat_id)
    if not arena:
        return "no_arena"
    if arena["phase"] != "lobby":
        return "closed"
    if user_id in arena["joueurs"]:
        return "already"
    if arena["mise"] > 0 and not db.ajuster_pts_brut(user_id, -arena["mise"]):
        return "no_pts"
    arena["joueurs"][user_id] = {"name": name, "pts": 0}
    arena["pot"] += arena["mise"]
    return "ok"

async def _arena_lobby_task(chat_id: int, bot):
    await asyncio.sleep(15)
    if ARENAS.get(chat_id, {}).get("phase") == "lobby":
        nb = len(ARENAS[chat_id]["joueurs"])
        await bot.send_message(chat_id,
            f"⏰ *15 secondes restantes !* ({nb} joueur(s) inscrit(s)) — /join pour participer !",
            parse_mode="Markdown")
    await asyncio.sleep(10)
    if ARENAS.get(chat_id, {}).get("phase") == "lobby":
        nb = len(ARENAS[chat_id]["joueurs"])
        await bot.send_message(chat_id,
            f"⚠️ *5 secondes !* ({nb} joueur(s)) — dernière chance !",
            parse_mode="Markdown")
    await asyncio.sleep(5)
    arena = ARENAS.get(chat_id)
    if not arena or arena["phase"] != "lobby":
        return
    if len(arena["joueurs"]) < 2:
        arena["phase"] = "termine"
        for uid in arena["joueurs"]:
            if arena["mise"] > 0:
                db.ajuster_pts_brut(uid, arena["mise"])
        await bot.send_message(chat_id,
            "❌ *Arène annulée* — pas assez de joueurs (minimum 2).\n_Mises remboursées._",
            parse_mode="Markdown")
        ARENAS.pop(chat_id, None)
        return
    arena["phase"] = "manche"
    nb  = len(arena["joueurs"])
    pot = arena["pot"]
    arena["manche_phase_max"] = 3 if nb == 2 else 5
    await bot.send_message(chat_id, msg.msg_arena_start(nb, arena["difficulte"], pot, arena["mise"]), parse_mode="Markdown")
    await asyncio.sleep(3)
    if chat_id in ARENAS:
        await _arena_start_round(chat_id, bot)

async def _arena_start_round(chat_id: int, bot):
    arena = ARENAS.get(chat_id)
    if not arena:
        return
    arena["manche"] += 1
    if not arena["duel_mode"]:
        arena["manche_phase"] += 1
    mot, anag = await start_round(chat_id, arena["difficulte"], bot, mode="arena")
    if arena["duel_mode"]:
        noms = [arena["joueurs"][uid]["name"] for uid in arena["duel_joueurs"] if uid in arena["joueurs"]]
        await bot.send_message(chat_id, msg.msg_arena_duel(noms, anag, arena["difficulte"], len(mot)), parse_mode="Markdown")
    else:
        await bot.send_message(chat_id, msg.msg_arena_manche(
            arena["manche_phase"], arena["manche_phase_max"],
            anag, arena["difficulte"], len(mot), arena["joueurs"]
        ), parse_mode="Markdown")
    start_tasks(chat_id, bot)

async def check_arena_answer(chat_id: int, user_id: str, user_name: str, texte: str, bot) -> bool:
    arena = ARENAS.get(chat_id)
    if not arena or arena["phase"] not in ("manche", "duel"):
        return False
    game = GAMES.get(chat_id)
    if not game or not game.get("actif"):
        return False
    if arena["duel_mode"] and user_id not in arena["duel_joueurs"]:
        return False
    if not arena["duel_mode"] and user_id not in arena["joueurs"]:
        return False
    if nettoyer(texte) != nettoyer(game["mot"]):
        return False

    game["actif"] = False
    _cancel_tasks_sync(chat_id)
    elapsed = time.time() - game["start_time"]
    pts = POINTS[arena["difficulte"]] + (1 if elapsed < BONUS_SPEED_SECONDS else 0)
    arena["joueurs"][user_id]["pts"] += pts

    if arena["duel_mode"]:
        nom = arena["joueurs"][user_id]["name"]
        await bot.send_message(chat_id,
            f"⚔️ *{nom}* remporte le duel ! +{pts} pt(s)\n🛡️ Badge Immunité gagné !",
            parse_mode="Markdown")
        db.add_consumable_badge(user_id, "🛡️ Immunité")
        perdants = [uid for uid in list(arena["duel_joueurs"]) if uid != user_id]
        arena["duel_mode"] = False
        arena["duel_joueurs"] = set()
        for i, uid in enumerate(perdants):
            await _arena_eliminer(chat_id, uid, bot, from_duel=True, chain=(i == len(perdants) - 1))
            if chat_id not in ARENAS:
                return True
    else:
        nom = arena["joueurs"][user_id]["name"]
        await bot.send_message(chat_id,
            f"🎯 *{nom}* remporte la manche ! +{pts} pt(s)",
            parse_mode="Markdown")
        await _arena_after_round(chat_id, bot, winner_id=user_id)
    return True

async def _arena_after_round(chat_id: int, bot, winner_id: str | None):
    arena = ARENAS.get(chat_id)
    if not arena:
        return
    joueurs = arena["joueurs"]
    if len(joueurs) <= 1:
        await _arena_end(chat_id, bot)
        return

    # Timeout pendant un duel → on relance le même duel
    if arena["duel_mode"]:
        await bot.send_message(chat_id, "⏱️ Personne n'a trouvé — le duel repart !")
        await asyncio.sleep(2)
        if chat_id in ARENAS:
            await _arena_start_round(chat_id, bot)
        return

    # Phase pas encore terminée → manche suivante
    if arena["manche_phase"] < arena["manche_phase_max"]:
        await asyncio.sleep(2)
        if chat_id in ARENAS:
            await _arena_start_round(chat_id, bot)
        return

    # Phase terminée — bilan et élimination
    scores_txt = "\n".join(
        f"• *{j['name']}* : {j['pts']} pt(s)"
        for j in sorted(joueurs.values(), key=lambda x: -x["pts"])
    )
    label = "Finale" if len(joueurs) == 2 else f"Phase ({arena['manche_phase_max']} manches)"
    await bot.send_message(chat_id,
        f"📊 *Bilan — {label}*\n{scores_txt}",
        parse_mode="Markdown")
    await asyncio.sleep(2)
    if chat_id not in ARENAS:
        return

    min_pts  = min(j["pts"] for j in joueurs.values())
    perdants = [uid for uid, j in joueurs.items() if j["pts"] == min_pts]

    if len(perdants) == len(joueurs):
        # Égalité parfaite → reset et rejouer la phase
        await bot.send_message(chat_id, "🤝 Égalité parfaite — on rejoue la phase !")
        arena["manche_phase"] = 0
        for uid in joueurs:
            joueurs[uid]["pts"] = 0
        await asyncio.sleep(2)
        if chat_id in ARENAS:
            await _arena_start_round(chat_id, bot)
    elif len(perdants) == 1:
        await _arena_eliminer(chat_id, perdants[0], bot)
    else:
        noms = [joueurs[uid]["name"] for uid in perdants]
        await bot.send_message(chat_id,
            f"⚔️ Égalité en bas du classement entre {' et '.join('*'+n+'*' for n in noms)} — *mort subite !*",
            parse_mode="Markdown")
        arena["duel_mode"] = True
        arena["duel_joueurs"] = set(perdants)
        await asyncio.sleep(3)
        if chat_id in ARENAS:
            await _arena_start_round(chat_id, bot)

async def _arena_eliminer(chat_id: int, user_id: str, bot, from_duel: bool = False, chain: bool = True):
    arena = ARENAS.get(chat_id)
    if not arena or user_id not in arena["joueurs"]:
        return

    is_finale = len(arena["joueurs"]) == 2  # immunité bloquée en finale

    # Immunité : bloquée en duel ET en finale
    if not from_duel and not is_finale and db.has_badge(user_id, "🛡️ Immunité"):
        db.remove_badge(user_id, "🛡️ Immunité")
        nom = arena["joueurs"][user_id]["name"]
        await bot.send_message(chat_id,
            f"🛡️ *Immunité activée !* *{nom}* échappe à l'élimination !",
            parse_mode="Markdown")
        autres = [(uid, j["pts"]) for uid, j in arena["joueurs"].items() if uid != user_id]
        if autres:
            autres.sort(key=lambda x: x[1])
            await _arena_eliminer(chat_id, autres[0][0], bot, from_duel=False, chain=chain)
        return

    nom = arena["joueurs"][user_id]["name"]
    arena["elimines"].append((user_id, nom))
    del arena["joueurs"][user_id]

    if len(arena["joueurs"]) == 1:
        # Winner takes all — pas de remboursement finaliste
        db.add_badges(user_id, ["🗡️ Finaliste"])
        await bot.send_message(chat_id,
            f"🗡️ *{nom}* est éliminé(e) — *Finaliste !* Badge 🗡️ décerné.",
            parse_mode="Markdown")
        await asyncio.sleep(2)
        await _arena_end(chat_id, bot)
    else:
        await bot.send_message(chat_id,
            f"💀 *{nom}* est éliminé(e) ! Il reste *{len(arena['joueurs'])}* joueur(s).",
            parse_mode="Markdown")
        if chain:
            # Reset de la phase pour les joueurs restants
            arena["manche_phase"] = 0
            arena["manche_phase_max"] = 3 if len(arena["joueurs"]) == 2 else 5
            for uid in arena["joueurs"]:
                arena["joueurs"][uid]["pts"] = 0
            nb = arena["manche_phase_max"]
            phase_label = "Finale" if nb == 3 else f"Phase suivante"
            await bot.send_message(chat_id,
                f"🔄 *{phase_label}* — {nb} manches avant la prochaine élimination.",
                parse_mode="Markdown")
            await asyncio.sleep(3)
            if chat_id in ARENAS:
                await _arena_start_round(chat_id, bot)

async def _arena_end(chat_id: int, bot):
    arena = ARENAS.get(chat_id)
    if not arena or not arena["joueurs"]:
        ARENAS.pop(chat_id, None)
        return
    winner_id   = list(arena["joueurs"].keys())[0]
    winner_name = arena["joueurs"][winner_id]["name"]
    pot         = arena["pot"]
    finaliste   = arena["elimines"][-1][1] if arena["elimines"] else ""
    if pot > 0:
        db.ajuster_pts_brut(winner_id, pot)
    db.add_badges(winner_id, ["🏟️ Gladiateur"])
    if arena["mise"] > 0:
        tous = [winner_id] + [uid for uid, _ in arena["elimines"]]
        for uid in tous:
            db.add_badges(uid, ["💰 Parieur"])
    await bot.send_message(chat_id, msg.msg_arena_fin(winner_name, finaliste, pot, arena["mise"]), parse_mode="Markdown")
    ARENAS.pop(chat_id, None)
    GAMES.pop(chat_id, None)

def arena_actif(chat_id: int) -> bool:
    return chat_id in ARENAS

# ── Stop ─────────────────────────────────────────────────────────
async def stop_game(chat_id: int) -> dict | None:
    game = GAMES.get(chat_id)
    if not game or not game.get("actif"):
        return None
    result = {
        "mot":            game["mot"],
        "mode":           game["mode"],
        "scores_tournoi": dict(game.get("scores_tournoi", {})),
    }
    game["actif"] = False
    _cancel_tasks_sync(chat_id)
    GAMES.pop(chat_id, None)
    return result
