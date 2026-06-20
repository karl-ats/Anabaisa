import os
import sys
import asyncio
import urllib.request
import json
import base64

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

# ── État global ──────────────────────────────────────────────────
BOT_EN_PAUSE = False

# ── Helpers ──────────────────────────────────────────────────────
def user_info(update: Update):
    u = update.effective_user
    return str(u.id), u.first_name or u.username or "Anonyme"

async def guard_pause(update: Update) -> bool:
    if BOT_EN_PAUSE:
        await update.message.reply_text("😴 Ana est en repos… Revenez plus tard !")
        return True
    return False

async def guard_no_game(update: Update, chat_id: int) -> bool:
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

def is_admin(user_id: str) -> bool:
    admin_id = os.environ.get("ADMIN_ID", "")
    return bool(admin_id) and str(user_id) == str(admin_id)

def extract_target(context) -> str | None:
    """Extrait la cible depuis les args : nom direct ou @mention."""
    if not context.args:
        return None
    raw = " ".join(context.args)
    # Retire le @ si présent en premier mot
    if context.args[0].startswith("@"):
        return context.args[0][1:] if len(context.args) == 1 else " ".join([context.args[0][1:]] + context.args[1:])
    return raw

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
        "• /indice — 💡 Un petit indice\n"
        "• /solution — 🏳️ Révéler la solution\n"
        "• /topscore — 🏛️ Classement all-time (points)\n"
        "• /topwin — 🏆 Classement all-time (victoires)\n"
        "• /profil — 👤 Tes stats et badges\n"
        "• /sabotage <nom> — 💣 Utiliser le badge Saboteur\n"
        "• /prestige <nom> — 👑 Utiliser le badge Prestige\n"
        "• /prolongation — ⏱️ Prolonger la partie en cours\n"
        "• /stop — ⛔ Arrêter la partie\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🌅 *Défi du jour automatique à 9h00 !*\n\n"
        "Alors, t'as ce qu'il faut pour me battre ? 😘",
        parse_mode="Markdown"
    )

async def cmd_starteasy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sched.register_chat(chat_id)
    if await guard_pause(update): return
    if await guard_no_game(update, chat_id): return
    mot, anag = await g.start_round(chat_id, "easy", context.bot)
    await update.message.reply_text(
        msg.msg_nouvelle_partie(anag, "easy", len(mot)),
        parse_mode="Markdown"
    )
    g.start_tasks(chat_id, context.bot)

async def cmd_startmedium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sched.register_chat(chat_id)
    if await guard_pause(update): return
    if await guard_no_game(update, chat_id): return
    mot, anag = await g.start_round(chat_id, "medium", context.bot)
    await update.message.reply_text(
        msg.msg_nouvelle_partie(anag, "medium", len(mot)),
        parse_mode="Markdown"
    )
    g.start_tasks(chat_id, context.bot)

async def cmd_starthard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sched.register_chat(chat_id)
    if await guard_pause(update): return
    if await guard_no_game(update, chat_id): return
    mot, anag = await g.start_round(chat_id, "hard", context.bot)
    await update.message.reply_text(
        msg.msg_nouvelle_partie(anag, "hard", len(mot)),
        parse_mode="Markdown"
    )
    g.start_tasks(chat_id, context.bot)

async def cmd_tournoi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sched.register_chat(chat_id)
    if await guard_pause(update): return
    if await guard_no_game(update, chat_id): return

    args = context.args
    if not args or args[0].lower() not in ("easy", "medium", "hard"):
        await update.message.reply_text("⚠️ Usage : /tournoi easy | medium | hard")
        return

    difficulte = args[0].lower()
    await g.start_tournament(chat_id, difficulte, context.bot)

async def cmd_indice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game    = g.GAMES.get(chat_id)
    if not game or not game.get("actif"):
        await update.message.reply_text("❌ Aucune partie en cours. Tapez /starteasy !")
        return
    # Annule les indices automatiques pour éviter les doublons
    g.cancel_hint_tasks(chat_id)
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
    await update.message.reply_text(
        msg.msg_solution(mot, "stop", mode),
        parse_mode="Markdown"
    )
    if mode == "tournament":
        await update.message.reply_text(
            msg.msg_fin_tournoi(scores),
            parse_mode="Markdown"
        )

# ── Classements ──────────────────────────────────────────────────
async def cmd_topscore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id, _ = user_info(update)
    classement, rang, mes_pts = db.get_topscore(chat_id, user_id)
    await update.message.reply_text(
        msg.msg_topscore(classement, rang, mes_pts),
        parse_mode="Markdown"
    )

async def cmd_topwin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id, _ = user_info(update)
    classement, rang, mes_victoires = db.get_topwin(chat_id, user_id)
    await update.message.reply_text(
        msg.msg_topwin(classement, rang, mes_victoires),
        parse_mode="Markdown"
    )

# ── Profil ───────────────────────────────────────────────────────
async def cmd_profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, _ = user_info(update)
    target_id = None

    # Cas 1 : reply sur le message d'un joueur → son profil
    reply = update.message.reply_to_message
    if reply and reply.from_user:
        target_id = str(reply.from_user.id)

    # Cas 2 : mention @nom via entity Telegram (text_mention = lien sans @username)
    if not target_id and update.message.entities:
        for entity in update.message.entities:
            if entity.type == "text_mention" and entity.user:
                target_id = str(entity.user.id)
                break

    if target_id:
        profil = db.get_profil(target_id)
        if not profil:
            await update.message.reply_text("❌ Ce joueur n'a pas encore joué !")
            return

    elif context.args:
        # Cas 3 : /profil @username ou /profil Prénom → recherche par nom
        target = extract_target(context)
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT user_id FROM joueurs WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                (f"%{target}%",)
            ).fetchone()
        if not row:
            await update.message.reply_text(f"❌ Joueur « {target} » introuvable.")
            return
        profil = db.get_profil(row["user_id"])

    else:
        # Cas 4 : son propre profil
        profil = db.get_profil(user_id)
        if not profil:
            await update.message.reply_text(
                "❌ Tu n'as pas encore joué ! Lance /starteasy pour commencer."
            )
            return

    await update.message.reply_text(
        msg.msg_profil(
            profil["name"], profil["pts_alltime"], profil["pts_hebdo"],
            profil["victoires"], profil["serie"], profil["badges"], profil["niveau"]
        ),
        parse_mode="Markdown"
    )

# ── Badge : Saboteur ─────────────────────────────────────────────
async def cmd_sabotage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, user_name = user_info(update)

    target = extract_target(context)
    if not target:
        await update.message.reply_text(
            "💣 Usage : `/sabotage <nom>` ou `/sabotage @pseudo`\n"
            "Retire *20 pts* au joueur ciblé et consomme ton badge 💣 Saboteur.\n"
            "_(La cible perd son badge 🛡️ Bouclier si elle en a un !)_",
            parse_mode="Markdown"
        )
        return

    resultat = db.utiliser_saboteur(user_id, target)

    if resultat["status"] == "no_badge":
        await update.message.reply_text(
            "❌ Tu ne possèdes pas le badge 💣 *Saboteur*.\n"
            "_Accumule 10 victoires d'affilée pour en obtenir un !_",
            parse_mode="Markdown"
        )
    elif resultat["status"] == "target_not_found":
        await update.message.reply_text(f"❌ Joueur « {target} » introuvable.")
    elif resultat["status"] == "multiple":
        noms = "\n".join(f"• {n}" for n in resultat["joueurs"])
        await update.message.reply_text(
            f"⚠️ Plusieurs joueurs correspondent à « {target} » :\n{noms}\n\nSois plus précis."
        )
    elif resultat["status"] == "self_target":
        await update.message.reply_text("😂 Tu ne peux pas te saboter toi-même !")
    elif resultat["status"] == "blocked":
        await update.message.reply_text(
            f"🛡️ *Sabotage bloqué !*\n\n"
            f"*{resultat['target_name']}* avait un 🛡️ Bouclier — il a absorbé l'attaque !\n"
            f"_Ton badge Saboteur a quand même été consommé._",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"💣 *Sabotage réussi !*\n\n"
            f"🎯 *{resultat['target_name']}* perd 20 pts\n"
            f"📉 {resultat['avant']} pts → {resultat['apres']} pts\n\n"
            f"_Ton badge Saboteur a été consommé._",
            parse_mode="Markdown"
        )

# ── Badge : Prestige ─────────────────────────────────────────────
async def cmd_prestige(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, user_name = user_info(update)

    target = extract_target(context)
    if not target:
        await update.message.reply_text(
            "👑 Usage : `/prestige <nom>` ou `/prestige @pseudo`\n"
            "Offre *30 pts* au joueur ciblé (prélevés sur ton score) et consomme ton badge 👑 Prestige.",
            parse_mode="Markdown"
        )
        return

    resultat = db.utiliser_prestige(user_id, target)

    if resultat["status"] == "no_badge":
        await update.message.reply_text(
            "❌ Tu ne possèdes pas le badge 👑 *Prestige*.\n"
            "_Ce badge est offert au champion de la semaine chaque lundi !_",
            parse_mode="Markdown"
        )
    elif resultat["status"] == "target_not_found":
        await update.message.reply_text(f"❌ Joueur « {target} » introuvable.")
    elif resultat["status"] == "multiple":
        noms = "\n".join(f"• {n}" for n in resultat["joueurs"])
        await update.message.reply_text(
            f"⚠️ Plusieurs joueurs correspondent à « {target} » :\n{noms}\n\nSois plus précis."
        )
    elif resultat["status"] == "self_target":
        await update.message.reply_text("😂 Tu ne peux pas te transférer des points à toi-même !")
    else:
        await update.message.reply_text(
            f"👑 *Prestige accordé !*\n\n"
            f"Tu offres *30 pts* à *{resultat['target_name']}*\n"
            f"_Ton badge Prestige a été consommé._",
            parse_mode="Markdown"
        )

# ── Badge : Prolongation ─────────────────────────────────────────
async def cmd_prolongation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id, _ = user_info(update)

    if not g.GAMES.get(chat_id, {}).get("actif"):
        await update.message.reply_text("❌ Aucune partie en cours à prolonger.")
        return

    if not db.has_badge(user_id, "⏱️ Prolongation"):
        await update.message.reply_text(
            "❌ Tu ne possèdes pas le badge ⏱️ *Prolongation*.\n"
            "_Ce badge est offert aux vainqueurs de tournoi !_",
            parse_mode="Markdown"
        )
        return

    db.remove_badge(user_id, "⏱️ Prolongation")
    ok = await g.extend_game(chat_id, 30, context.bot)
    if ok:
        await update.message.reply_text(
            "⏱️ *Prolongation activée !* +30 secondes sur le chrono.\n"
            "_Ton badge Prolongation a été consommé._",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Impossible de prolonger la partie.")

RELEASE_MESSAGE = """🆕 *Ana s'est mis à jour !*

🏆 *Classements par groupe*
/topscore et /topwin sont maintenant filtrés par groupe + ton rang personnel s'affiche.

🎖️ *Nouveaux badges*
💥 Doubleur — 7 victoires d'affilée : double tes pts sur le prochain mot
🔄 Renaissance — 15 d'affilée : survit à une défaite (série repart à 1)
🛡️ Bouclier — tous les 25 victoires : bloque un Sabotage
⏱️ Prolongation — vainqueur de tournoi : +30s sur la partie
👑 Prestige — champion de la semaine : transfère 30 pts à qui tu veux

Les badges en double s'affichent maintenant *Saboteur x2* dans ton profil.

📌 *Nouvelles commandes*
/topscore — classement all-time points
/topwin — classement all-time victoires
/profil @nom — voir le profil d'un autre joueur
/prestige — offrir 30 pts à un joueur
/prolongation — prolonger la partie active

💡 /indice ne déclenche plus les indices automatiques en double.

Bonne chance ! 😏"""

# ── Commande admin : broadcast ───────────────────────────────────
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, _ = user_info(update)
    if not is_admin(user_id):
        await update.message.reply_text(
            f"🚫 Commande réservée à l'admin.\n_(ton ID : `{user_id}`)_",
            parse_mode="Markdown"
        )
        return

    texte = " ".join(context.args) if context.args else RELEASE_MESSAGE

    chats = db.get_all_chats()
    ok, ko, errors = 0, 0, []
    for chat_id in chats:
        try:
            await context.bot.send_message(chat_id, texte, parse_mode="Markdown")
            ok += 1
        except Exception as e:
            errors.append(f"• `{chat_id}` : {e}")
            ko += 1

    rapport = f"📣 Broadcast terminé : {ok} envoyé(s), {ko} échec(s)."
    if errors:
        rapport += "\n\n*Erreurs :*\n" + "\n".join(errors[:10])
    await update.message.reply_text(rapport, parse_mode="Markdown")

# ── Commande admin : pull GitHub + restart ───────────────────────
async def cmd_pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, _ = user_info(update)
    admin_id = os.environ.get("ADMIN_ID", "")

    if not admin_id:
        await update.message.reply_text(
            f"⚙️ *ADMIN\\_ID non configuré.*\n\n"
            f"Ton ID Telegram est : `{user_id}`\n\n"
            f"Copie ce nombre et configure-le comme secret `ADMIN_ID` dans Render.",
            parse_mode="Markdown"
        )
        return

    if not is_admin(user_id):
        await update.message.reply_text(
            f"🚫 Commande réservée à l'admin.\n_(ton ID : `{user_id}`)_",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text("⏳ Pull GitHub en cours…")

    try:
        token = os.environ.get("GITHUB_TOKEN", "")

        req = urllib.request.Request(
            "https://api.github.com/repos/karl-ats/Anabaisa/commits?per_page=1",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        )
        with urllib.request.urlopen(req) as r:
            commits = json.loads(r.read())
        latest_sha = commits[0]["sha"][:10]
        latest_msg = commits[0]["commit"]["message"].split("\n")[0]

        req2 = urllib.request.Request(
            f"https://api.github.com/repos/karl-ats/Anabaisa/commits/{latest_sha}",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        )
        with urllib.request.urlopen(req2) as r:
            commit_data = json.loads(r.read())
        files = [f["filename"] for f in commit_data["files"] if f["status"] != "removed" and f["filename"].endswith(".py")]

        workdir = os.path.dirname(os.path.abspath(__file__))
        for filename in files:
            req3 = urllib.request.Request(
                f"https://api.github.com/repos/karl-ats/Anabaisa/contents/{filename}?ref=main",
                headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            )
            with urllib.request.urlopen(req3) as r:
                data = json.loads(r.read())
            content = base64.b64decode(data["content"]).decode("utf-8")
            with open(os.path.join(workdir, filename), "w", encoding="utf-8") as f:
                f.write(content)

        await update.message.reply_text(
            f"✅ *Pull réussi !*\n"
            f"🔖 `{latest_sha}` — {latest_msg}\n"
            f"📄 Fichiers : `{'`, `'.join(files)}`\n\n"
            f"♻️ Redémarrage dans 2 secondes…",
            parse_mode="Markdown"
        )
        await asyncio.sleep(2)
        os._exit(0)

    except Exception as e:
        await update.message.reply_text(f"❌ Erreur lors du pull : {e}")

# ── Commande admin : statut du bot ───────────────────────────────
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, _ = user_info(update)
    if not is_admin(user_id):
        await update.message.reply_text(
            f"🚫 Commande réservée à l'admin.\n_(ton ID : `{user_id}`)_",
            parse_mode="Markdown"
        )
        return

    try:
        token = os.environ.get("GITHUB_TOKEN", "")
        req = urllib.request.Request(
            "https://api.github.com/repos/karl-ats/Anabaisa/commits?per_page=1",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        )
        with urllib.request.urlopen(req) as r:
            commits = json.loads(r.read())
        sha = commits[0]["sha"][:10]
        commit_msg = commits[0]["commit"]["message"].split("\n")[0]
        commit_date = commits[0]["commit"]["committer"]["date"][:10]
    except Exception:
        sha, commit_msg, commit_date = "?", "Impossible de joindre GitHub", "?"

    parties_actives = [(cid, g.GAMES[cid]) for cid in g.GAMES if g.GAMES[cid].get("actif")]
    nb_chats_total = len(sched.REGISTERED_CHATS)

    lines = [
        "🤖 *Statut du bot Ana*",
        "",
        f"🔖 *Version :* `{sha}` — {commit_msg} ({commit_date})",
        "",
        f"💬 *Chats enregistrés :* {nb_chats_total}",
        f"🎮 *Parties en cours :* {len(parties_actives)}",
    ]
    for cid, game in parties_actives:
        mode_label = {"quick": "Rapide", "tournament": "Tournoi", "daily": "Défi"}.get(game.get("mode", ""), game.get("mode", ""))
        lines.append(f"   • Chat `{cid}` — {mode_label} · {game.get('difficulte', '?')} · `{game.get('anagramme', '?').upper()}`")

    lines += ["", f"⏰ *Prochain défi du jour :* 9h00 ({sched.REGISTERED_CHATS and 'actif' or 'aucun chat'})"]

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ── Commande admin : pause / wake ───────────────────────────────
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_EN_PAUSE
    user_id, _ = user_info(update)
    if not is_admin(user_id):
        await update.message.reply_text(
            f"🚫 Commande réservée à l'admin.\n_(ton ID : `{user_id}`)_",
            parse_mode="Markdown"
        )
        return
    BOT_EN_PAUSE = True
    await update.message.reply_text("😴 Ana est en repos…")

async def cmd_wake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_EN_PAUSE
    user_id, _ = user_info(update)
    if not is_admin(user_id):
        await update.message.reply_text(
            f"🚫 Commande réservée à l'admin.\n_(ton ID : `{user_id}`)_",
            parse_mode="Markdown"
        )
        return
    BOT_EN_PAUSE = False
    await update.message.reply_text("😏 Ana est de retour !")

# ── Commande admin : retirer des points à un joueur ──────────────
async def cmd_retirer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, _ = user_info(update)
    if not is_admin(user_id):
        await update.message.reply_text(
            f"🚫 Commande réservée à l'admin.\n_(ton ID : `{user_id}`)_",
            parse_mode="Markdown"
        )
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "ℹ️ Usage : `/retirer <nom|id> <points>`\nEx : `/retirer Karl 200`",
            parse_mode="Markdown"
        )
        return

    *nom_parts, pts_str = context.args
    nom = " ".join(nom_parts)
    try:
        montant = int(pts_str)
        if montant <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Le montant doit être un entier positif.")
        return

    resultat = db.retirer_points_joueur(nom, montant)

    if resultat["status"] == "not_found":
        await update.message.reply_text(f"❌ Aucun joueur trouvé pour « {nom} ».")
    elif resultat["status"] == "multiple":
        noms = "\n".join(f"• {n}" for n in resultat["joueurs"])
        await update.message.reply_text(
            f"⚠️ Plusieurs joueurs correspondent à « {nom} » :\n{noms}\n\nSois plus précis.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"⚖️ *Points retirés*\n\n"
            f"👤 *{resultat['name']}*\n"
            f"📉 {resultat['avant']} pts → {resultat['apres']} pts\n"
            f"🔻 -{montant} pts",
            parse_mode="Markdown"
        )

# ── Handler texte (vérification réponse) ────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if BOT_EN_PAUSE:
        return
    chat_id   = update.effective_chat.id
    user_id, user_name = user_info(update)
    texte     = update.message.text
    await g.check_answer(chat_id, user_id, user_name, texte, context.bot)

# ── Main ─────────────────────────────────────────────────────────
def main():
    db.init_db()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",        cmd_start))
    app.add_handler(CommandHandler("startAna",     cmd_start))
    app.add_handler(CommandHandler("starteasy",    cmd_starteasy))
    app.add_handler(CommandHandler("startmedium",  cmd_startmedium))
    app.add_handler(CommandHandler("starthard",    cmd_starthard))
    app.add_handler(CommandHandler("tournoi",      cmd_tournoi))
    app.add_handler(CommandHandler("indice",       cmd_indice))
    app.add_handler(CommandHandler("solution",     cmd_solution))
    app.add_handler(CommandHandler("stop",         cmd_stop))
    app.add_handler(CommandHandler("topscore",     cmd_topscore))
    app.add_handler(CommandHandler("topwin",       cmd_topwin))
    app.add_handler(CommandHandler("profil",       cmd_profil))
    app.add_handler(CommandHandler("sabotage",     cmd_sabotage))
    app.add_handler(CommandHandler("prestige",     cmd_prestige))
    app.add_handler(CommandHandler("prolongation", cmd_prolongation))
    app.add_handler(CommandHandler("broadcast",    cmd_broadcast))
    app.add_handler(CommandHandler("pause",        cmd_pause))
    app.add_handler(CommandHandler("wake",         cmd_wake))
    app.add_handler(CommandHandler("pull",         cmd_pull))
    app.add_handler(CommandHandler("status",       cmd_status))
    app.add_handler(CommandHandler("retirer",      cmd_retirer))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    sched.start_scheduler(app.bot)

    print("🤖 Bot Anagramme v3 démarré !")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
