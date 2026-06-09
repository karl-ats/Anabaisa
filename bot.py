from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

from config import TELEGRAM_TOKEN
import database as db
import messages as msg
import game as g
import scheduler as sched

# ── Helpers ──────────────────────────────────────────────────────
def user_info(update: Update):
    u = update.effective_user
    return str(u.id), u.first_name or u.username or "Anonyme"

async def guard_no_game(update: Update, chat_id: int) -> bool:
    """Retourne True si une partie est déjà active (et envoie un message)."""
    game = g.GAMES.get(chat_id)
    if game and game.get("actif"):
        anag = game["anagramme"]
        mode = game["mode"]
        label = {"quick": "partie rapide", "tournament": "tournoi", "daily": "défi du jour"}.get(mode, "partie")
        await update.message.reply_text(
            f"⚠️ Une {label} est déjà en cours !\n"
            f"Anagramme : *{anag.upper()}*\n\n"
            f"Tapez /stop pour l'arrêter.",
            parse_mode="Markdown"
        )
        return True
    return False

# ── Commandes de base ─────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sched.register_chat(chat_id)
    user = update.effective_user
    prenom = user.first_name if user and user.first_name else "toi"
    await update.message.reply_text(
        f"😏 *Oh, {prenom}... tu viens jouer avec moi ?*\n\n"
        "Je suis *Ana*, ton bot anagramme préféré — et je t'avertis, je ne suis pas facile à avoir… 😈\n\n"
        "Je vais te mélanger les lettres, te faire chauffer les neurones et peut-être même te laisser gagner… si tu es sage. 🔥\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎮 *Parties rapides :*\n"
        "• /starteasy — 😊 Facile (≤6 lettres · 1 pt)\n"
        "• /startmedium — 🔥 Moyen (7–9 lettres · 2 pts)\n"
        "• /starthard — 💀 Difficile (10+ lettres · 3 pts)\n\n"
        "🏟️ *Tournois :*\n"
        "• /tournoi easy | medium | hard\n\n"
        "📋 *Autres :*\n"
        "• /indice — 💡 Un petit indice (juste pour toi 😉)\n"
        "• /solution — 🏳️ Révéler la solution\n"
        "• /scores — 🏆 Classements hebdo + all-time\n"
        "• /stop — ⛔ Arrêter la partie\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🌅 *Défi du jour automatique à 9h00 !*\n\n"
        "Alors, t'as ce qu'il faut pour me battre ? 😘",
        parse_mode="Markdown"
    )

async def cmd_starteasy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sched.register_chat(chat_id)
    if await guard_no_game(update, chat_id):
        return
    mot, anag = await g.start_round(chat_id, "easy", context.bot)
    await update.message.reply_text(
        msg.msg_nouvelle_partie(anag, "easy", len(mot)),
        parse_mode="Markdown"
    )
    g.start_tasks(chat_id, context.bot)

async def cmd_startmedium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sched.register_chat(chat_id)
    if await guard_no_game(update, chat_id):
        return
    mot, anag = await g.start_round(chat_id, "medium", context.bot)
    await update.message.reply_text(
        msg.msg_nouvelle_partie(anag, "medium", len(mot)),
        parse_mode="Markdown"
    )
    g.start_tasks(chat_id, context.bot)

async def cmd_starthard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sched.register_chat(chat_id)
    if await guard_no_game(update, chat_id):
        return
    mot, anag = await g.start_round(chat_id, "hard", context.bot)
    await update.message.reply_text(
        msg.msg_nouvelle_partie(anag, "hard", len(mot)),
        parse_mode="Markdown"
    )
    g.start_tasks(chat_id, context.bot)

async def cmd_tournoi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sched.register_chat(chat_id)
    if await guard_no_game(update, chat_id):
        return

    args = context.args
    if not args or args[0].lower() not in ("easy", "medium", "hard"):
        await update.message.reply_text(
            "⚠️ Usage : /tournoi easy | medium | hard"
        )
        return

    difficulte = args[0].lower()
    await g.start_tournament(chat_id, difficulte, context.bot)

async def cmd_indice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game    = g.GAMES.get(chat_id)
    if not game or not game.get("actif"):
        await update.message.reply_text("❌ Aucune partie en cours. Tapez /starteasy !")
        return
    result = g.give_hint(chat_id)
    if result is None:
        max_h = g.MAX_HINTS.get(game["difficulte"], 1)
        await update.message.reply_text(
            f"🚫 Maximum d'indices atteint ({max_h}/{max_h}). Cherche encore ! 😏"
        )
        return
    masque, count, max_h = result
    await update.message.reply_text(
        msg.msg_indice(masque, len(game["mot"]), count, max_h),
        parse_mode="Markdown"
    )

async def cmd_solution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    info = await g.stop_game(chat_id)
    if info is None:
        await update.message.reply_text("❌ Aucune partie en cours.")
        return
    await update.message.reply_text(
        msg.msg_solution(info["mot"], "manual", info["mode"]),
        parse_mode="Markdown"
    )

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    info = await g.stop_game(chat_id)
    if info is None:
        await update.message.reply_text("❌ Aucune partie en cours.")
        return
    mot    = info["mot"]
    mode   = info["mode"]
    scores = info["scores_tournoi"]
    # Toujours montrer le mot (que la partie soit encore active ou déjà expirée)
    await update.message.reply_text(
        msg.msg_solution(mot, "stop", mode),
        parse_mode="Markdown"
    )
    # Si c'était un tournoi, afficher le bilan des scores
    if mode == "tournament":
        await update.message.reply_text(
            msg.msg_fin_tournoi(scores),
            parse_mode="Markdown"
        )

async def cmd_scores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hebdo   = db.get_classement_hebdo()
    alltime = db.get_classement_alltime()
    await update.message.reply_text(
        msg.msg_scores(hebdo, alltime),
        parse_mode="Markdown"
    )

# ── Handler texte (vérification réponse) ────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    chat_id   = update.effective_chat.id
    user_id, user_name = user_info(update)
    texte     = update.message.text
    await g.check_answer(chat_id, user_id, user_name, texte, context.bot)

# ── Main ─────────────────────────────────────────────────────────
def main():
    db.init_db()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("startAna",    cmd_start))
    app.add_handler(CommandHandler("starteasy",   cmd_starteasy))
    app.add_handler(CommandHandler("startmedium", cmd_startmedium))
    app.add_handler(CommandHandler("starthard",   cmd_starthard))
    app.add_handler(CommandHandler("tournoi",     cmd_tournoi))
    app.add_handler(CommandHandler("indice",      cmd_indice))
    app.add_handler(CommandHandler("solution",    cmd_solution))
    app.add_handler(CommandHandler("stop",        cmd_stop))
    app.add_handler(CommandHandler("scores",      cmd_scores))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Scheduler (défi du jour, résultats, champion semaine)
    sched.start_scheduler(app.bot)

    print("🤖 Bot Anagramme v2 démarré !")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
