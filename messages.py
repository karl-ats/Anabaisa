import random
from config import POINTS, BONUS_SPEED_SECONDS, hint_timing_str

# ── Relances taquines ───────────────────────────────────────────
TAUNTS = [
    "😴 Vous dormez ou quoi ? C'est pas si dur !",
    "🤔 Toujours personne... le chat a avalé vos cerveaux ?",
    "👀 Je vous vois hésiter... lancez-vous !",
    "😏 C'est un mot français, promis. Cherchez encore !",
    "🦗 ...Crickets. Quelqu'un est encore là ?",
    "🧠 Faites chauffer les neurones, ça commence à sentir le brûlé !",
    "⏳ Le temps tourne... et vous, vous rêvez ?",
    "🙈 Personne ? Vraiment personne ? Même pas un essai ?",
]

# ── Réactions selon la vitesse ─────────────────────────────────
def reaction_vitesse(secondes: float) -> str:
    if secondes < 5:
        return "⚡ *ÉCLAIR !* Incroyable, tu l'as eu en moins de 5 secondes !"
    elif secondes < 10:
        return "🔥 *Fulgurant !* Quelle rapidité !"
    elif secondes < 20:
        return "😎 *Bien joué !* Tu n'as pas traîné."
    elif secondes < 30:
        return "😏 *Tranquille...* Mais c'est trouvé, ça compte !"
    else:
        return "😅 *Enfin !* On commençait à désespérer !"

# ── Message victoire ────────────────────────────────────────────
def msg_victoire(prenom: str, mot: str, secondes: float, points_gagnes: int, total: int, niveau: str, bonus: bool, mode: str = "quick") -> str:
    reaction = reaction_vitesse(secondes)
    bonus_txt = f"\n🎁 *+1 bonus vitesse* (trouvé en moins de {BONUS_SPEED_SECONDS}s) !" if bonus else ""
    suite = "" if mode in ("tournament", "daily") else "\n\nTapez /starteasy · /startmedium · /starthard pour continuer !"
    return (
        f"🎉 *{prenom}* a trouvé *{mot.upper()}* !\n"
        f"{reaction}\n"
        f"{bonus_txt}\n"
        f"💰 *+{points_gagnes} pt{'s' if points_gagnes > 1 else ''}* → Total : *{total} pts*\n"
        f"🏅 Niveau : {niveau}"
        f"{suite}"
    )

# ── Message nouvelle partie ─────────────────────────────────────
def msg_nouvelle_partie(anagramme: str, difficulte: str, nb_lettres: int) -> str:
    labels = {"easy": "😊 Facile", "medium": "🔥 Moyen", "hard": "💀 Difficile"}
    pts    = POINTS[difficulte]
    return (
        f"🔤 *Nouvelle anagramme !*\n\n"
        f"➡️  *{anagramme.upper()}*\n\n"
        f"📏 {nb_lettres} lettres · {labels[difficulte]} · *{pts} pt{'s' if pts > 1 else ''}*\n"
        f"_({hint_timing_str(difficulte)})_"
    )

# ── Message indice ──────────────────────────────────────────────
def msg_indice(masque: str, nb_lettres: int, count: int = 1, max_h: int = 1) -> str:
    return f"💡 *Indice {count}/{max_h} :* `{masque}`  ({nb_lettres} lettres)"

# ── Message solution ────────────────────────────────────────────
def msg_solution(mot: str, raison: str = "timeout", mode: str = "quick") -> str:
    if raison == "timeout":
        intro = "⏰ *Temps écoulé !* Personne n'a trouvé..."
    elif raison == "stop":
        intro = "🛑 *Partie arrêtée.*"
    else:
        intro = "🔓 *Solution révélée.*"
    suite = "" if mode in ("tournament", "daily") else "\n\nTapez /starteasy · /startmedium · /starthard !"
    return f"{intro}\n\nLe mot était : *{mot.upper()}*{suite}"

# ── Tournoi ─────────────────────────────────────────────────────
def msg_debut_tournoi(difficulte: str, nb_manches: int) -> str:
    labels = {"easy": "😊 Facile", "medium": "🔥 Moyen", "hard": "💀 Difficile"}
    return (
        f"🏟️ *TOURNOI {labels[difficulte].upper()} !*\n\n"
        f"📋 *{nb_manches} manches* vont s'enchaîner.\n"
        f"🏆 Le joueur avec le plus de points à la fin remporte le tournoi !\n\n"
        f"Préparez-vous... la première manche arrive dans *3 secondes* !"
    )

def msg_manche(numero: int, total: int, anagramme: str, difficulte: str, nb_lettres: int) -> str:
    labels = {"easy": "😊 Facile", "medium": "🔥 Moyen", "hard": "💀 Difficile"}
    pts = POINTS[difficulte]
    return (
        f"🎯 *Manche {numero}/{total}*\n\n"
        f"➡️  *{anagramme.upper()}*\n\n"
        f"📏 {nb_lettres} lettres · {labels[difficulte]} · *{pts} pt{'s' if pts > 1 else ''}*\n"
        f"_({hint_timing_str(difficulte)})_"
    )

def msg_fin_tournoi(scores_tournoi: dict) -> str:
    if not scores_tournoi:
        return "🏁 *Tournoi terminé !* Personne n'a marqué de points cette fois... 😅"

    classement = sorted(scores_tournoi.items(), key=lambda x: x[1]["pts"], reverse=True)
    medailles  = ["🥇", "🥈", "🥉"]
    lignes     = ["🏁 *TOURNOI TERMINÉ — Classement final* 🏁\n"]

    for i, (uid, info) in enumerate(classement):
        med = medailles[i] if i < 3 else f"{i+1}."
        lignes.append(f"{med} *{info['name']}* — {info['pts']} pts")

    gagnant = classement[0][1]["name"]
    lignes.append(f"\n🎊 Félicitations à *{gagnant}* pour cette victoire !")
    return "\n".join(lignes)

# ── Classements ─────────────────────────────────────────────────
def msg_scores(hebdo: list, alltime: list) -> str:
    medailles = ["🥇", "🥈", "🥉"]

    def format_liste(joueurs):
        if not joueurs:
            return "_Aucun score encore_"
        lignes = []
        for i, j in enumerate(joueurs[:10]):
            med = medailles[i] if i < 3 else f"{i+1}."
            lignes.append(f"{med} *{j['name']}* — {j['points']} pts · {j['niveau']}")
        return "\n".join(lignes)

    return (
        f"📊 *CLASSEMENT HEBDOMADAIRE* (reset lundi)\n\n"
        f"{format_liste(hebdo)}\n\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"🏛️ *CLASSEMENT ALL-TIME*\n\n"
        f"{format_liste(alltime)}"
    )

# ── Défi du jour ─────────────────────────────────────────────────
def msg_defi_du_jour(anagramme: str, difficulte: str, nb_lettres: int) -> str:
    labels = {"easy": "😊 Facile", "medium": "🔥 Moyen", "hard": "💀 Difficile"}
    pts = POINTS[difficulte]
    return (
        f"🌅 *DÉFI DU JOUR !*\n\n"
        f"➡️  *{anagramme.upper()}*\n\n"
        f"📏 {nb_lettres} lettres · {labels[difficulte]} · *{pts} pt{'s' if pts > 1 else ''}*\n\n"
        f"_({hint_timing_str(difficulte)})_\n\n"
        f"Soyez le premier à trouver ce mot !"
    )

def msg_vainqueur_jour(nom: str, mot: str, pts: int) -> str:
    return (
        f"🌙 *Résultat du défi du jour !*\n\n"
        f"🏆 Vainqueur : *{nom}*\n"
        f"💡 Le mot était : *{mot.upper()}*\n"
        f"💰 Points gagnés : *{pts}*\n\n"
        f"Rendez-vous demain à 9h pour le prochain défi ! 🌅"
    )

def msg_defi_non_resolu(mot: str) -> str:
    return (
        f"🌙 *Résultat du défi du jour*\n\n"
        f"😔 Personne n'a trouvé le mot du jour...\n"
        f"💡 La réponse était : *{mot.upper()}*\n\n"
        f"On se rattrape demain à 9h ! 💪"
    )

def msg_champion_semaine(nom: str, pts: int) -> str:
    return (
        f"🏆 *CHAMPION DE LA SEMAINE !*\n\n"
        f"👑 *{nom}* remporte la semaine avec *{pts} points* !\n\n"
        f"Bravo ! Une nouvelle semaine commence... Qui sera le prochain champion ? 🎯"
    )

def msg_relance() -> str:
    return random.choice(TAUNTS)

# ── Profil joueur ────────────────────────────────────────────────
def msg_profil(name: str, pts_alltime: int, pts_hebdo: int, victoires: int, serie: int, badges: list, niveau: str) -> str:
    badges_str = "  ".join(badges) if badges else "_Aucun badge encore_"
    return (
        f"👤 *Profil de {name}*\n\n"
        f"🏅 Niveau : {niveau}\n"
        f"💰 Points all-time : *{pts_alltime} pts*\n"
        f"📅 Points cette semaine : *{pts_hebdo} pts*\n"
        f"🏆 Victoires : *{victoires}*\n"
        f"🔥 Série en cours : *{serie}*\n\n"
        f"🎖️ *Badges :*\n{badges_str}"
    )

# ── Montée de niveau ─────────────────────────────────────────────
def msg_level_up(prenom: str, nouveau_niveau: str) -> str:
    return (
        f"🆙 *MONTÉE DE NIVEAU !*\n\n"
        f"*{prenom}* atteint le rang *{nouveau_niveau}* ! 🎊\n"
        f"Continue comme ça !"
    )

# ── Nouveau badge ────────────────────────────────────────────────
def msg_nouveaux_badges(prenom: str, badges: list) -> str:
    s = "s" if len(badges) > 1 else ""
    badges_str = "  ".join(badges)
    return f"🎖️ *Badge{s} débloqué{s} pour {prenom} !* {badges_str}"
