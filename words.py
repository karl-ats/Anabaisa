import random

# Mots classés par difficulté — tous vérifiés sans accents
# easy   : 4-6 lettres (vrais mots français)
# medium : 7-9 lettres
# hard   : 10+ lettres

WORDS = {
    "easy": [
        # animaux
        "chat", "chien", "lapin", "souris", "renard", "loup", "ours", "lion",
        "singe", "girafe", "tigre", "zebre", "truite", "carpe", "poule",
        "mouton", "canard",
        # nature
        "arbre", "fleur", "herbe", "tige", "foret", "ocean", "sable",
        "rocher", "pierre", "vallee", "desert", "glace", "neige", "pluie",
        "vent", "brume", "lune", "etoile",
        # corps
        "main", "pied", "tete", "bras", "face", "oeil", "nez", "dent",
        "gorge", "ventre", "genou", "talon", "doigt", "langue", "bouche",
        # nourriture / boissons
        "pain", "lait", "oeuf", "miel", "sucre", "sel", "beurre", "farine",
        "huile", "gateau", "fraise", "cerise", "pomme", "poire", "orange",
        "citron", "mangue", "raisin", "olive", "tomate", "oignon", "salade",
        "biere", "cidre", "cafe", "sirop", "creme",
        # vie quotidienne
        "table", "chaise", "porte", "lampe", "livre", "stylo", "gomme",
        "crayon", "cahier", "ecole", "route", "avion", "train", "bateau",
        "verre", "coeur", "maison", "jardin",
        # couleurs
        "rouge", "bleu", "vert", "jaune", "blanc", "noir", "rose",
        # temps / saisons
        "nuit", "matin", "ete", "hiver", "lundi", "mardi", "jeudi",
        "samedi", "mars", "avril", "juin", "aout",
        # émotions / idées
        "amour", "paix", "joie", "rire", "fete", "reve", "espoir",
        # santé
        "virus", "venin", "poison", "remede", "vaccin", "piqure",
        "muscle", "sang", "poumon", "foie", "rein", "toxine",
        # divers
        "chant", "danse", "sport", "film", "photo", "soleil", "oiseau",
        "nuage", "fleuve", "cheval", "plage", "coton", "alcool",
    ],

    "medium": [
        # animaux
        "elephant", "panthere", "dauphin", "baleine", "pintade", "cameleon",
        "perroquet", "moustique", "ecureuil", "herisson", "gorille",
        "hamster", "vautour", "scorpion",
        # nature / géo
        "montagne", "riviere", "glacier", "savanne", "cyclone", "ouragan",
        "horizon", "paysage",
        # objets / lieux
        "escalier", "horloge", "lanterne", "pendule", "tableau", "parasol",
        "palmier", "mosquee", "village", "veranda", "immeuble", "logiciel",
        "guitare", "tambour", "sifflet",
        # concepts / qualités
        "harmonie", "sagesse", "silence", "patience", "richesse", "tendresse",
        "serenite", "illusion", "evasion", "victoire", "fantome", "symbole",
        "message", "exemple", "formule", "mystere",
        # actions / états
        "imaginer", "partager", "embarquer", "enchanter", "entendre",
        # mots courants
        "journee", "semaine", "vacances", "souvenir", "surprise", "question",
        "spectacle", "festival", "carnaval", "champion", "medaille",
        "tournesol", "pyramide", "diamant", "cristal", "drapeau", "royaume",
        "diplome", "enigme", "galaxie", "planete", "meteore", "univers",
        "origami", "pirouette", "plongeon", "rectangle", "triangle",
        "noisette", "vanille", "saucisse", "chocolat",
        # santé / corps
        "estomac", "hygiene", "identite", "pharmacie", "vitamine",
        # travail / société
        "domicile", "emission", "ecologie", "fabrique", "gardien",
        "magicien", "menuisier", "jongleur", "artisan", "reunion",
        "peinture", "portrait", "librairie", "numerique",
        "obstacle", "organique", "robotique", "transport", "nautique",
        "petanque", "pilotage", "physique",
        # divers
        "chouette", "licorne", "girafon", "flamant", "rossignol",
        "ruisseau", "rondelle", "limaces", "lionnes", "magnolia",
        "majeste", "marathon", "parfumer", "parachute", "poudriere",
        "grillage", "glissade", "ficelle", "farouche", "forgeron",
        "gazeuse", "arpege", "arsenal", "arsenic",
        "arrivee", "arrosage", "artichaut", "arrosoir", "ardoise",
        "argument", "armement", "armoire", "armurier", "accident",
        "activite", "addition", "affiche", "alliance", "ambition",
        "amusement", "analyse", "angoisse", "animation",
        "appareil", "appetit", "apprenti", "approche", "arbitre",
        "archange", "archerie", "archipel", "arctique",
    ],

    "hard": [
        # mots réels 10+ lettres
        "bibliothecaire", "extraordinaire", "environnement", "accomplissement",
        "administration", "apprentissage", "archeologique", "architecture",
        "arrondissement", "astronomique", "authentification", "autobiographie",
        "bureaucratique", "caracteristique", "catastrophique", "christianisme",
        "cinematographe", "classification", "collaborateur", "communication",
        "comprehension", "concentration", "confidentialite", "connaissance",
        "consideration", "construction", "contradiction", "contribution",
        "cooperation", "correspondance", "cristallisation", "decentralisation",
        "deforestation", "democratisation", "developpement", "differenciation",
        "discrimination", "documentation", "electricite", "emancipation",
        "encombrement", "enseignement", "enthousiasme", "entrepreneuriat",
        "experimentation", "fonctionnement", "franchissement", "gouvernement",
        "hallucination", "harmonisation", "hospitalisation", "humanitaire",
        "identification", "illumination", "imagination", "implementation",
        "independance", "informatique", "infrastructure", "institutionnel",
        "interdependance", "interpretation", "investigation", "liberalisation",
        "magnetophone", "manifestation", "mathematiques", "metamorphose",
        "meteorologie", "microbiologie", "modernisation", "mondialisation",
        "multiplication", "nationalisation", "negociation", "observation",
        "optimisation", "organisation", "paleontologie", "participation",
        "personnalisation", "philanthropie", "photosynthese", "planification",
        "polarisation", "popularisation", "preoccupation", "privatisation",
        "professionnalisme", "programmation", "proliferation", "psychologique",
        "radicalisation", "rationalisation", "rehabilitation", "representation",
        "responsabilite", "restructuration", "satisfaction", "scolarisation",
        "sensibilisation", "simplification", "socialisation", "sophistication",
        "spiritualite", "standardisation", "stratification", "structuration",
        "subordination", "symbolisation", "systematisation", "technologique",
        "telecommunication", "transformation", "transparence", "uniformisation",
        "valorisation", "verification", "vulgarisation", "acceleration",
        "acceptation", "accentuation", "accelerateur", "accessibilite",
        "acclimatation", "accompagnement", "accommodation",
        # mots déplacés depuis medium (trop longs)
        "volcanique", "appartement",
    ],
}

def get_word(difficulty: str) -> str:
    return random.choice(WORDS[difficulty])
