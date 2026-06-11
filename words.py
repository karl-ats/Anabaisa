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
        "hibou", "aigle", "faucon", "lezard", "cobra", "bison", "phoque",
        "loutre", "castor", "vipere", "cerf", "cygne", "mulot", "mulet",
        "caille", "paon", "morse",
        # nature
        "arbre", "fleur", "herbe", "tige", "foret", "ocean", "sable",
        "rocher", "pierre", "vallee", "desert", "glace", "neige", "pluie",
        "vent", "brume", "lune", "etoile",
        "dune", "mont", "mare", "ruche", "cactus", "tulipe", "graine",
        "saison", "lierre", "lagon", "etang", "delta", "liane", "marais",
        "limon", "bocage",
        # corps
        "main", "pied", "tete", "bras", "face", "oeil", "nez", "dent",
        "gorge", "ventre", "genou", "talon", "doigt", "langue", "bouche",
        "coude", "paume", "pouce", "hanche", "epaule", "nuque", "joue",
        "front", "crane", "tempe", "levre",
        # nourriture / boissons
        "pain", "lait", "oeuf", "miel", "sucre", "sel", "beurre", "farine",
        "huile", "gateau", "fraise", "cerise", "pomme", "poire", "orange",
        "citron", "mangue", "raisin", "olive", "tomate", "oignon", "salade",
        "biere", "cidre", "cafe", "sirop", "creme",
        "melon", "noix", "figue", "prune", "datte", "mais", "soupe",
        "poulet", "boeuf", "veau", "jambon", "yaourt", "bonbon", "ananas",
        "banane", "epice", "moule", "navet", "radis", "poivre",
        # maison / objets
        "table", "chaise", "porte", "lampe", "livre", "stylo", "gomme",
        "crayon", "cahier", "ecole", "route", "avion", "train", "bateau",
        "verre", "coeur", "maison", "jardin",
        "four", "miroir", "rideau", "canape", "tapis", "store", "tiroir",
        "balai", "savon", "brosse", "nappe", "dalle", "tuile", "vitre",
        "clef", "cadre",
        # couleurs
        "rouge", "bleu", "vert", "jaune", "blanc", "noir", "rose",
        "beige", "gris", "mauve", "lilas", "brun", "ocre", "indigo",
        # temps / saisons
        "nuit", "matin", "ete", "hiver", "lundi", "mardi", "jeudi",
        "samedi", "mars", "avril", "juin", "aout",
        # émotions / idées
        "amour", "paix", "joie", "rire", "fete", "reve", "espoir",
        "colere", "peur", "honte", "calme", "grace", "force", "fierte",
        "lutte", "larme", "heros", "mythe", "magie", "fable",
        # santé
        "virus", "venin", "poison", "remede", "vaccin", "piqure",
        "muscle", "sang", "poumon", "foie", "rein", "toxine",
        # école / culture
        "regle", "carte", "image", "atlas", "globe", "classe", "eleve",
        "lecon", "devoir", "examen", "conte", "poeme", "roman",
        # transport / lieux
        "metro", "moto", "velo", "camion", "fusee", "navire",
        "port", "pont", "salon", "bureau", "ferme", "usine", "cave",
        # matériaux / construction
        "acier", "bronze", "brique",
        # musique / arts
        "piano", "flute", "harpe", "chant", "danse",
        # divers
        "sport", "film", "photo", "soleil", "oiseau",
        "nuage", "fleuve", "cheval", "plage", "coton", "alcool",
        "jouet", "ballon", "bague", "montre", "cadeau", "casque",
        "linge", "champ", "bulle", "ecume", "fosse", "bande", "equipe",
        "tribu", "comte", "prince",
    ],

    "medium": [
        # animaux
        "elephant", "panthere", "dauphin", "baleine", "pintade", "cameleon",
        "perroquet", "moustique", "ecureuil", "herisson", "gorille",
        "hamster", "vautour", "scorpion",
        "colibri", "gazelle", "mouette", "hermine", "marsouin", "blaireau",
        "araignee", "oisillon", "mesange", "fourmis", "alouette",
        # nature / géo
        "montagne", "riviere", "glacier", "savanne", "cyclone", "ouragan",
        "horizon", "paysage",
        "falaise", "caverne", "lavande", "fenouil", "liseron",
        "luciole", "feuillage", "jonquille", "clairiere", "fontaine",
        # objets / lieux
        "escalier", "horloge", "lanterne", "pendule", "tableau", "parasol",
        "palmier", "mosquee", "village", "veranda", "immeuble", "logiciel",
        "guitare", "tambour", "sifflet",
        "chapeau", "chemise", "chiffre", "machine", "dossier", "grenier",
        "lucarne", "gobelet", "gondole", "matelas", "calepin", "caravane",
        "boussole", "ceinture", "couronne", "clavecin", "brochure",
        "orchidee", "chandelle", "cimetiere", "chaussure", "corbeille",
        # concepts / qualités
        "harmonie", "sagesse", "silence", "patience", "richesse", "tendresse",
        "serenite", "illusion", "evasion", "victoire", "fantome", "symbole",
        "message", "exemple", "formule", "mystere",
        "courage", "liberte", "logique", "legende", "murmure", "noblesse",
        "mystique", "detente", "melange", "lumiere", "monnaie",
        # actions / états
        "imaginer", "partager", "embarquer", "enchanter", "entendre",
        # nourriture
        "noisette", "vanille", "saucisse", "chocolat",
        "abricot", "brioche", "dessert", "fromage", "confiture", "mandarine",
        "langouste",
        # mots courants
        "journee", "semaine", "vacances", "souvenir", "surprise", "question",
        "spectacle", "festival", "carnaval", "champion", "medaille",
        "tournesol", "pyramide", "diamant", "cristal", "drapeau", "royaume",
        "diplome", "enigme", "galaxie", "planete", "meteore", "univers",
        "origami", "pirouette", "plongeon", "rectangle", "triangle",
        "concert", "circuit", "cuisine", "escrime", "essence",
        "matelot", "monstre", "discours", "distance", "naufrage",
        "nocturne", "comedien", "comedie", "confort", "cortege", "coutume",
        "copilote", "courrier", "cycliste", "coiffeur", "chevalier",
        "comptable", "douanier", "duchesse", "cerisier", "chaperon",
        "chasseur", "charade", "citoyen", "merveille", "fantaisie",
        "colombier", "manivelle", "etincelle", "mollusque", "jardinier",
        # santé / corps
        "estomac", "hygiene", "identite", "pharmacie", "vitamine",
        "nombril", "octopus",
        # travail / société
        "domicile", "emission", "ecologie", "fabrique", "gardien",
        "magicien", "menuisier", "jongleur", "artisan", "reunion",
        "peinture", "portrait", "librairie", "numerique",
        "obstacle", "organique", "robotique", "transport", "nautique",
        "petanque", "pilotage", "physique",
        "musique", "chaleur", "basilic", "cascade",
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
        "olivier", "originel",
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
        # ajouts
        "abominable", "abstraction", "adolescence", "admirateur", "adversaire",
        "affirmation", "alimentaire", "amelioration", "amplification",
        "anthropologie", "antibiotique", "appartenance", "appreciation",
        "appropriation", "approximation", "artificielle", "assimilation",
        "association", "attachement", "bienveillance", "biodiversite",
        "bienfaisance", "capitalisme", "celebration", "changement",
        "circonstance", "citoyennete", "civilisation", "clarification",
        "collectivite", "commentaire", "completement", "comportement",
        "confirmation", "confrontation", "consommation", "coordination",
        "criminologie", "declaration", "denomination", "determination",
        "devastation", "distribution", "domination", "echantillon",
        "elaboration", "electricien", "elimination", "equivalence",
        "eradication", "excentrique", "exclamation", "exploitation",
        "exploration", "fabrication", "fascination", "fermentation",
        "fondamental", "fraternite", "hierarchie", "hydrologie",
        "hypocrisie", "immigration", "imperialisme", "inconscience",
        "indignation", "inflammation", "information", "ingenierie",
        "innovation", "installation", "integration", "intervention",
        "intimidation", "introduction", "legislation", "legitimite",
        "memorisation", "mobilisation", "modification", "motivation",
        "notification", "numerisation", "objectivite", "orchestration",
        "orientation", "oscillation", "pacification", "panoramique",
        "pathologique", "perseverance", "perturbation", "population",
        "precipitation", "preservation", "proclamation", "production",
        "profondeur", "propagation", "protestation", "publication",
        "purification", "qualification", "radioactivite", "rayonnement",
        "renversement", "solidarite", "souverainete", "speculation",
        "stimulation", "supplication", "surveillance", "technologie",
        "totalitarisme", "transposition", "triangulation", "urbanisation",
        "utilisation", "vaccination",
    ],
}

def get_word(difficulty: str) -> str:
    return random.choice(WORDS[difficulty])
