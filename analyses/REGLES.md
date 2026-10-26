# Compte rendu après chaque match : procédure et règles

**Mode actuel : brouillon validé par Tony.** Quand Tony écrit « match enregistré », Claude (dans la conversation, pas en tâche programmée) suit les étapes 2 et 3.1 à 3.5 ci-dessous avec `render --dry-run` : le script contrôle le texte et l'affiche **sans rien écrire**. Tony relit, demande des changements si besoin ; ce n'est qu'après son accord explicite que Claude relance `render` sans `--dry-run`, puis publie (étape 3.6). La tâche programmée « Compte rendu automatique SCB » est **désactivée** : si on la réactive un jour, elle publiera sans validation, comme décrit ci-dessous.

La procédure ci-dessous peut aussi être exécutée par une tâche programmée de Claude (sans personne pour valider). Elle suit **à la lettre** les étapes ci-dessous. En cas de doute ou d'échec, **on ne publie rien** et on explique pourquoi dans le message final.

## Contexte

Équipe de volley SCB. Après chaque match, Antoine saisit les stats sur `/saisie/`, elles arrivent dans la base Supabase (projet `dglmohqqoidmdiirriul`). Ce compte rendu est lu par **toute l'équipe** (public du dashboard, niveaux variés, ton enthousiaste). Il s'affiche dans l'onglet « Dernier match » du dashboard à partir du fichier `analyses/index.json` de ce dépôt (GitHub `tonycha-prog/scb-stats-2026`, publié par Vercel).

## Étapes

1. **Dépôt.** Attache le dépôt avec `add_repo` (owner `tonycha-prog`, repo `scb-stats-2026`, `access: push`), clone-le avec `git clone --depth 1 https://github.com/tonycha-prog/scb-stats-2026 /home/claude/scb-stats-2026` (timeout généreux, une seule fois) puis `register_repo_root`.
2. **Y a-t-il un match à traiter ?** Avec l'outil SQL Supabase (`execute_sql`, projet `dglmohqqoidmdiirriul`) :
   `select match_id from public.matchs m where exists (select 1 from public.sets s where s.match_id = m.match_id) order by 1;`
   Lis `analyses/index.json`. Les matchs à traiter sont ceux dont le numéro est `>= a_partir_du_match`, et **sans** entrée dans `analyses`. S'il n'y en a aucun : termine par une ligne « Rien à faire » (sans rien modifier).
   Si l'outil Supabase n'est pas disponible dans cette session : arrête-toi et dis-le. Ne tente rien d'autre pour obtenir les données.
3. **Pour chaque match à traiter, du plus ancien au plus récent :**
   1. Exécute la requête du fichier `analyses/requete_donnees.sql` avec `execute_sql`. Le résultat est une colonne `data_json` contenant un objet JSON. Écris cet objet **tel quel**, sans rien modifier, dans `/tmp/data.json` (outil Write).
   2. Lance `python3 analyses/faits.py facts /tmp/data.json --match N --out /tmp/facts.json`.
      - Si le script signale une erreur de somme de contrôle, les données ont été mal recopiées : refais la requête et réécris le fichier. **Ne corrige jamais un chiffre à la main.** Après 2 échecs : arrête-toi, ne publie rien.
   3. Lis `/tmp/facts.json` en entier. Il contient : `match`, `equipe` (pour chaque indicateur : valeur du match, moyenne des matchs d'avant, tendance), `joueurs` (avec `eligible` et les indicateurs disponibles), `evolution` (match par match) et `ids` (la liste des références utilisables).
   4. Rédige `/tmp/report.json` en respectant le schéma et les règles d'écriture ci-dessous.
   5. Lance `python3 analyses/faits.py render /tmp/facts.json /tmp/report.json --index analyses/index.json`.
      - Si le script répond « REFUSÉ », corrige le rapport selon les messages et relance (4 essais maximum). Si le rapport reste refusé : ne publie rien, arrête-toi, explique pourquoi.
   6. `git add analyses/index.json`, `git commit` (message : « Compte rendu du match N »), `git fetch origin main` puis rebase si besoin, `git push origin main`. Ne modifie aucun autre fichier.
4. **Message final** (3 lignes maximum) : quel(s) match(s) traité(s), publié ou non, et s'il y a eu un blocage.

## Schéma de `/tmp/report.json`

```json
{
  "match_id": 3,
  "titre": "Titre court et vivant (80 caractères max.)",
  "equipe": ["2 à 4 phrases : l'analyse de la performance de l'équipe, comparée au reste de la saison"],
  "points_forts": ["1 à 3 phrases : ce qui a bien marché"],
  "focus": {
    "titre": "Le focus du prochain entraînement, en quelques mots",
    "pourquoi": "Pourquoi ce choix, en s'appuyant sur les chiffres",
    "exercice": "Un exercice concret, expliqué simplement"
  },
  "saison": ["1 à 3 phrases : l'évolution depuis le début de la saison"],
  "joueurs": [ { "joueur": "Prénom", "point_fort": "…", "axe": "…" } ]
}
```

## Règles d'écriture (le script les contrôle en partie)

**Aucun chiffre écrit en dur, jamais.** Pas de « 3 sets », « 10 minutes », « 40 % ». Les chiffres s'écrivent uniquement avec des références `{{identifiant}}` choisies dans la liste `ids` de `facts.json`, par exemple :
- `{{match.score}}` (le score en sets), `{{match.adv}}` (l'adversaire), `{{match.resultat}}`
- `{{eq.att_marque.match}}` (la valeur de ce match), `{{eq.att_marque.saison}}` (moyenne des matchs d'avant), `{{eq.att_marque.ecart}}` (l'écart, sans signe : dis toi-même « mieux » ou « moins bien » selon la tendance), `{{eq.att_marque.m1}}`, `{{eq.att_marque.m2}}`… (valeur de chaque match, pour parler d'évolution)
- `{{j.Prénom.def_ok.match}}`, `{{j.Prénom.def_ok.saison}}`… pour un joueur
Tu ne calcules rien toi-même. Si tu as besoin d'un chiffre qui n'existe pas dans `ids`, reformule sans chiffre. Pas de référence à un indicateur d'un joueur qui n'a pas assez d'actions (elle est absente de la liste, et le script la refuse).

**Ton : positif, encourageant, simple.** Écris pour des gens de tous niveaux, y compris des enfants de dix ans : phrases courtes, mots simples, pas de jargon (explique en quelques mots ce que veut dire « réception réussie » si tu l'utilises). Enthousiaste sans exagérer : une défaite n'est pas un drame, une victoire n'est pas une démonstration.
- Ne blâme jamais un joueur. Ne compare jamais deux joueurs entre eux.
- Pour un joueur, l'« axe » est une chose à travailler, formulée comme une action (« chercher… », « continuer à… », « essayer de… »). N'y cite **jamais** un chiffre faible de ce joueur.
- Le « point fort » doit être vrai d'après `facts.json` : appuie-le sur un indicateur dont la tendance est « mieux », ou sur une valeur clairement bonne. N'invente rien qui ne soit pas dans les faits (pas d'ambiance, d'intention ni de cause cachée).
- Mots interdits (le script les refuse) : nul, mauvais, catastrophe, honteux, décevant, incapable, fautif, raté, désastre, faiblesse, échec, etc. Parle de « ballons à gagner », de « marges de progrès ».
- Échantillons petits : un match, ce sont quelques dizaines de ballons par joueur. Pas de conclusion sur une cause. Reste mesuré (« on a vu », « ça semble »).

**Choix du focus d'entraînement (un seul).** Cherche, dans `equipe`, l'indicateur « moins bien » le plus net et qui peut se travailler en une séance (réception, défense, service, attaque). Vérifie dans `evolution` qu'il est régulier sur plusieurs matchs, pas un accident. Si rien n'est « moins bien », prends l'indicateur qui progresse le moins ou le plus utile à consolider. L'exercice : un jeu ou une situation simple et concrète, sans chiffre.

**Équipe et saison.** Compare le match à la moyenne des matchs d'avant (`saison`). Si `nb_matchs_avant` vaut 0, ne compare à rien : parle seulement de ce match et du point de départ. Pour l'évolution, n'utilise que les références `m<numéro>` qui existent.

**Blocs.** `blocs_set` = blocs réussis par set (point au bloc + ballon touché qui ne marque pas). Cette stat n'est suivie que depuis le match 4 : si elle est absente des `ids`, n'en parle pas, et ne la compare jamais à une période où elle n'était pas suivie (le script ne donne alors pas de valeur « saison »).

**Joueurs.** Une entrée pour chaque joueur « eligible », ni plus ni moins, avec exactement les prénoms de `facts.json`. Antoine (libéro) : ses indicateurs sont surtout la réception et la défense.

## Garde-fous

- Cette tâche ne modifie **que** `analyses/index.json`, et seulement via le script `render`. Elle n'écrit rien dans la base Supabase.
- Un compte rendu déjà publié n'est jamais remplacé par cette tâche. Pour le masquer, mettre `"masque": true` dans son entrée ; pour le régénérer, supprimer son entrée de `analyses/index.json`.
- Si quoi que ce soit paraît anormal (données incohérentes, outil manquant, script en erreur), ne publie rien et dis-le.
