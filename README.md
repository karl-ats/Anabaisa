# 🔤 Bot Anagramme Telegram v2

Bot Telegram de jeu d'anagrammes en français avec 3 niveaux, tournois, classements hebdo/all-time et défi du jour automatique.

---

## 📁 Structure du projet

```
anagram_bot/
├── bot.py            # Point d'entrée, handlers Telegram
├── config.py         # Constantes et configuration
├── database.py       # Accès SQLite (joueurs, scores, défis)
├── game.py           # Logique de jeu (parties, tournois)
├── scheduler.py      # Tâches automatiques (APScheduler)
├── messages.py       # Tous les textes du bot
├── words.py          # Listes de mots par difficulté
├── requirements.txt
├── render.yaml       # Configuration déploiement Render
└── README.md
```

---

## ⚙️ Installation locale

### 1. Prérequis
- Python 3.11+
- Token Telegram → [@BotFather](https://t.me/BotFather)

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 3. Lancer le bot
```bash
export TELEGRAM_TOKEN="ton_token_ici"
python bot.py
```

---

## 🎮 Commandes

| Commande | Description | Points |
|----------|-------------|--------|
| `/starteasy` | 😊 Mot ≤ 6 lettres | 1 pt |
| `/startmedium` | 🔥 Mot 7–9 lettres | 2 pts |
| `/starthard` | 💀 Mot 10+ lettres | 3 pts |
| `/tournoi easy\|medium\|hard` | Série de 5 manches | cumulés |
| `/indice` | Révèle 1ère et dernière lettre | — |
| `/solution` | Révèle le mot | — |
| `/scores` | Classements hebdo + all-time | — |
| `/stop` | Arrête la partie en cours | — |

---

## ⏱️ Chrono par partie

| Délai | Événement |
|-------|-----------|
| 8s | Message de relance taquin |
| 10s | Indice automatique |
| 30s | Solution automatique |

**Bonus vitesse :** trouver en moins de 5s = +1 pt bonus !

---

## 🏅 Niveaux & Badges

| Niveau | Seuil |
|--------|-------|
| 🐣 Débutant | 0 pt |
| 📚 Amateur | 10 pts |
| 🧠 Expert | 30 pts |
| 👑 Maître des mots | 75 pts |

**Badges spéciaux :**
- ⚡ *Foudre de guerre* — 5 victoires consécutives
- 🌙 *Noctambule* — Victoire entre minuit et 5h
- 🎯 *Sans indice* — Trouvé avant l'indice automatique

---

## 🌅 Automatisations (UTC+1 Yaoundé)

| Heure | Événement |
|-------|-----------|
| 9h00 chaque jour | Défi du jour (difficulté aléatoire) |
| 21h00 chaque jour | Annonce du vainqueur du défi |
| Lundi 9h00 | Champion de la semaine + reset hebdo |

---

## 🚀 Déploiement sur Render

### 1. Pousser le code sur GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/TON_USER/anagram-bot.git
git push -u origin main
```

### 2. Créer un service sur Render
1. Va sur [render.com](https://render.com) → **New → Blueprint**
2. Connecte ton repo GitHub
3. Render détecte automatiquement le `render.yaml`
4. Dans **Environment Variables**, ajoute : `TELEGRAM_TOKEN = ton_token`
5. Clique **Deploy**

> Le disque `/data/anagram.db` est persistant : les scores survivent aux redémarrages.

---

## ➕ Ajouter des mots

Dans `words.py`, ajoute tes mots dans la liste correspondante :
```python
WORDS = {
    "easy":   ["maison", "jardin", ...],   # ≤ 6 lettres
    "medium": ["elephant", ...],            # 7–9 lettres
    "hard":   ["extraordinaire", ...],      # 10+ lettres
}
```
