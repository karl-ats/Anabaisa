import asyncio
import random
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import DAILY_HOUR, DAILY_MINUTE, RESULT_HOUR, RESULT_MINUTE, TIMEZONE
import database as db
import messages as msg
from words import get_word
from game import melanger, start_round, start_tasks, GAMES

# chat_ids enregistrés — persistés en DB, rechargés au démarrage
REGISTERED_CHATS: set = set()

def register_chat(chat_id: int):
    if chat_id not in REGISTERED_CHATS:
        REGISTERED_CHATS.add(chat_id)
        db.save_chat(chat_id)

def load_registered_chats():
    REGISTERED_CHATS.clear()
    REGISTERED_CHATS.update(db.get_all_chats())

# ── Défi du jour ─────────────────────────────────────────────────
async def _send_defi_to_chat(chat_id: int, bot, mot: str, anag: str, difficulte: str):
    if GAMES.get(chat_id, {}).get("actif"):
        return  # Ne pas interrompre une partie en cours
    await start_round(chat_id, difficulte, bot, mode="daily", mot=mot)
    await bot.send_message(
        chat_id,
        msg.msg_defi_du_jour(anag, difficulte, len(mot)),
        parse_mode="Markdown"
    )
    start_tasks(chat_id, bot)

async def send_daily_challenge(bot):
    today      = date.today().isoformat()
    difficulte = random.choice(["easy", "medium", "hard"])
    mot        = get_word(difficulte)
    anag       = melanger(mot)

    db.save_defi(today, mot, difficulte)

    chats = list(REGISTERED_CHATS)
    results = await asyncio.gather(
        *[_send_defi_to_chat(c, bot, mot, anag, difficulte) for c in chats],
        return_exceptions=True
    )
    for chat_id, result in zip(chats, results):
        if isinstance(result, Exception):
            print(f"[Scheduler] Erreur défi chat {chat_id}: {result}")

async def send_daily_result(bot):
    today = date.today().isoformat()
    defi  = db.get_defi(today)
    if not defi:
        return

    mot = defi["mot"]

    async def _send(chat_id):
        if defi["gagnant_id"]:
            nom = db.get_joueur_name(defi["gagnant_id"])
            await bot.send_message(
                chat_id,
                msg.msg_vainqueur_jour(nom, mot, defi["pts_gagnes"] or 0),
                parse_mode="Markdown"
            )
        else:
            await bot.send_message(
                chat_id,
                msg.msg_defi_non_resolu(mot),
                parse_mode="Markdown"
            )

    chats = list(REGISTERED_CHATS)
    results = await asyncio.gather(
        *[_send(c) for c in chats], return_exceptions=True
    )
    for chat_id, result in zip(chats, results):
        if isinstance(result, Exception):
            print(f"[Scheduler] Erreur résultat défi chat {chat_id}: {result}")

# ── Champion de la semaine (lundi 9h) ────────────────────────────
async def send_weekly_champion(bot):
    champion = db.get_champion_semaine()

    async def _send(chat_id):
        if champion:
            await bot.send_message(
                chat_id,
                msg.msg_champion_semaine(champion["name"], champion["pts"]),
                parse_mode="Markdown"
            )
        else:
            await bot.send_message(
                chat_id,
                "📊 *Fin de semaine !* Pas assez de parties cette semaine... On se rattrape !",
                parse_mode="Markdown"
            )

    chats = list(REGISTERED_CHATS)
    results = await asyncio.gather(
        *[_send(c) for c in chats], return_exceptions=True
    )
    for chat_id, result in zip(chats, results):
        if isinstance(result, Exception):
            print(f"[Scheduler] Erreur champion chat {chat_id}: {result}")

    if champion:
        db.add_consumable_badge(champion["user_id"], "👑 Prestige")

    db.reset_hebdo()

# ── Démarrage scheduler ───────────────────────────────────────────
def start_scheduler(bot) -> AsyncIOScheduler:
    load_registered_chats()

    tz        = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        send_daily_challenge,
        CronTrigger(hour=DAILY_HOUR, minute=DAILY_MINUTE, timezone=tz),
        args=[bot],
        id="daily_challenge",
        replace_existing=True,
    )

    scheduler.add_job(
        send_daily_result,
        CronTrigger(hour=RESULT_HOUR, minute=RESULT_MINUTE, timezone=tz),
        args=[bot],
        id="daily_result",
        replace_existing=True,
    )

    scheduler.add_job(
        send_weekly_champion,
        CronTrigger(day_of_week="mon", hour=DAILY_HOUR, minute=DAILY_MINUTE, timezone=tz),
        args=[bot],
        id="weekly_champion",
        replace_existing=True,
    )

    scheduler.start()
    print(f"[Scheduler] Démarré. {len(REGISTERED_CHATS)} chats chargés. Défi du jour à {DAILY_HOUR}h{DAILY_MINUTE:02d} ({TIMEZONE})")
    return scheduler
