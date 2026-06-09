import random
import asyncio
from datetime import date, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import DAILY_HOUR, DAILY_MINUTE, RESULT_HOUR, RESULT_MINUTE, TIMEZONE
import database as db
import messages as msg
from words import get_word
from game import melanger, start_round, start_tasks

# chat_ids enregistrés (rempli au démarrage ou via /register)
REGISTERED_CHATS: set = set()

def register_chat(chat_id: int):
    REGISTERED_CHATS.add(chat_id)

# ── Défi du jour ─────────────────────────────────────────────────
async def send_daily_challenge(bot):
    today      = date.today().isoformat()
    difficulte = random.choice(["easy", "medium", "hard"])
    mot        = get_word(difficulte)
    anag       = melanger(mot)

    db.save_defi(today, mot, difficulte)

    for chat_id in REGISTERED_CHATS:
        try:
            await start_round(chat_id, difficulte, bot, mode="daily")
            await bot.send_message(
                chat_id,
                msg.msg_defi_du_jour(anag, difficulte, len(mot)),
                parse_mode="Markdown"
            )
            start_tasks(chat_id, bot)
        except Exception as e:
            print(f"[Scheduler] Erreur défi du jour chat {chat_id}: {e}")

async def send_daily_result(bot):
    today = date.today().isoformat()
    defi  = db.get_defi(today)
    if not defi:
        return

    mot = defi["mot"]

    for chat_id in REGISTERED_CHATS:
        try:
            if defi["gagnant_id"]:
                with db.get_conn() as conn:
                    row = conn.execute(
                        "SELECT name FROM joueurs WHERE user_id = ?",
                        (defi["gagnant_id"],)
                    ).fetchone()
                nom = row["name"] if row else "Inconnu"
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
        except Exception as e:
            print(f"[Scheduler] Erreur résultat défi chat {chat_id}: {e}")

# ── Champion de la semaine (lundi 9h) ────────────────────────────
async def send_weekly_champion(bot):
    champion = db.get_champion_semaine()
    for chat_id in REGISTERED_CHATS:
        try:
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
        except Exception as e:
            print(f"[Scheduler] Erreur champion semaine chat {chat_id}: {e}")

    db.reset_hebdo()

# ── Démarrage scheduler ───────────────────────────────────────────
def start_scheduler(bot) -> AsyncIOScheduler:
    tz        = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    # Défi du jour — 9h00
    scheduler.add_job(
        send_daily_challenge,
        CronTrigger(hour=DAILY_HOUR, minute=DAILY_MINUTE, timezone=tz),
        args=[bot],
        id="daily_challenge",
        replace_existing=True,
    )

    # Résultat du défi — 21h00
    scheduler.add_job(
        send_daily_result,
        CronTrigger(hour=RESULT_HOUR, minute=RESULT_MINUTE, timezone=tz),
        args=[bot],
        id="daily_result",
        replace_existing=True,
    )

    # Champion de la semaine — lundi 9h00
    scheduler.add_job(
        send_weekly_champion,
        CronTrigger(day_of_week="mon", hour=DAILY_HOUR, minute=DAILY_MINUTE, timezone=tz),
        args=[bot],
        id="weekly_champion",
        replace_existing=True,
    )

    scheduler.start()
    print(f"[Scheduler] Démarré. Défi du jour à {DAILY_HOUR}h{DAILY_MINUTE:02d} ({TIMEZONE})")
    return scheduler
