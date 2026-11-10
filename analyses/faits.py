#!/usr/bin/env python3
"""
SCB – calcul des faits chiffrés et contrôle des comptes rendus automatiques.

Principe : l'IA rédige, mais ne cite JAMAIS un chiffre elle-même. Elle écrit des
références {{id}} ; ce script les remplace par les valeurs qu'il a calculées, et
refuse tout texte qui contient un chiffre en dur, un mot interdit, ou une
référence à un joueur / une statistique sans assez d'actions.

Commandes
  faits.py facts  data.json --match N [--out facts.json]
  faits.py render facts.json report.json --index analyses/index.json [--dry-run]
  faits.py todo   data.json analyses/index.json         (matchs sans compte rendu)
"""
import argparse, json, math, re, sys, datetime

SUMCOLS = ["serv_nb", "serv_aces", "serv_adv_diff", "serv_fautes", "serv_neutres",
           "att_nb", "att_points", "att_adv_diff", "att_fautes", "att_bloquees", "point_bloc",
           "rec_plus_passeur", "rec_moy_tmoy", "rec_moins_manquee",
           "def_ok_passeur", "def_tmoy", "def_moins_manquee",
           "rel_plus_passeur", "rel_moy", "autres_fautes",
           # blocs touchés (bloc réussi sans point) : suivis depuis le match 4 ; null = non suivi
           "bloc_touche", "point_bloc_suivi"]

# id, libellé, format, "plus c'est haut mieux c'est", (colonne d'échantillon, minimum pour un joueur)
METRICS = {
    "pts_set":        ("points directs par set", "dec", True,  ("sets", 2)),
    "fautes_set":     ("fautes directes par set", "dec", False, ("sets", 2)),
    "serv_pression":  ("services qui mettent l'adversaire en difficulté", "pct", True, ("serv_nb", 6)),
    "serv_fautes_pct": ("services fautifs", "pct", False, ("serv_nb", 6)),
    "att_marque":     ("attaques qui marquent", "pct", True, ("att_nb", 10)),
    "eff_att":        ("efficacité en attaque", "pct", True, ("att_nb", 10)),
    "att_fautes_pct": ("attaques fautives", "pct", False, ("att_nb", 10)),
    "rec_reussie":    ("réceptions réussies", "pct", True, ("rec_n", 6)),
    "rec_manquee":    ("réceptions manquées", "pct", False, ("rec_n", 6)),
    "def_ok":         ("défenses ok", "pct", True, ("def_n", 6)),
    "def_jouable":    ("défenses jouables", "pct", True, ("def_n", 6)),
    "def_manquee":    ("défenses manquées", "pct", False, ("def_n", 6)),
    "rel_passeur":    ("relances pile sur le passeur", "pct", True, ("rel_n", 4)),
    "coeff_pf":       ("points marqués pour une faute (coefficient points / fautes)", "dec", True, ("sets", 2)),
    "blocs_set":      ("blocs réussis par set (point au bloc ou ballon touché)", "dec", True, ("sets_bloc", 2)),
}

BANNED = [r"nul(le|s|les)?", r"mauvais(e|es)?", r"catastroph\w*", r"horribl\w*", r"honteu\w*", r"pire(s)?",
          r"décevan\w*", r"incapable\w*", r"fautif(s|ve|ves)?", r"coupable\w*", r"raté(s|e|es)?", r"désastr\w*",
          r"médiocr\w*", r"inadmissible\w*", r"lamentabl\w*", r"faiblesse(s)?", r"minable\w*",
          r"il faut arrêter", r"n'importe quoi", r"échec(s)?", r"à cause de lui", r"à cause d'elle"]


# ----------------------------------------------------------------- calculs
def div(a, b):
    return a / b if b else None


def derive(s):
    """s : dictionnaire de sommes (+ 'sets'). Retourne les indicateurs."""
    g = lambda k: s.get(k, 0) or 0
    rec = g("rec_plus_passeur") + g("rec_moy_tmoy") + g("rec_moins_manquee")
    dfn = g("def_ok_passeur") + g("def_tmoy") + g("def_moins_manquee")
    rel = g("rel_plus_passeur") + g("rel_moy")
    fautes = g("serv_fautes") + g("att_fautes") + g("autres_fautes")
    pts = g("serv_aces") + g("att_points") + g("point_bloc")
    sets = g("sets")
    d = {
        "sets": sets, "serv_nb": g("serv_nb"), "att_nb": g("att_nb"), "rec_n": rec, "def_n": dfn, "rel_n": rel,
        "pts_set": div(pts, sets), "fautes_set": div(fautes, sets),
        "pts_total": pts, "fautes_total": fautes, "coeff_pf": div(pts, fautes),
        "serv_pression": div(g("serv_aces") + g("serv_adv_diff"), g("serv_nb")),
        "serv_fautes_pct": div(g("serv_fautes"), g("serv_nb")),
        "att_marque": div(g("att_points"), g("att_nb")),
        "eff_att": div(g("att_points") - g("att_fautes") - g("att_bloquees"), g("att_nb")),
        "att_fautes_pct": div(g("att_fautes"), g("att_nb")),
        "rec_reussie": div(g("rec_plus_passeur"), rec), "rec_manquee": div(g("rec_moins_manquee"), rec),
        "def_ok": div(g("def_ok_passeur"), dfn), "def_jouable": div(g("def_ok_passeur") + g("def_tmoy"), dfn),
        "def_manquee": div(g("def_moins_manquee"), dfn),
        "rel_passeur": div(g("rel_plus_passeur"), rel),
        "sets_bloc": g("sets_bloc"),
        "blocs_set": div(g("point_bloc_suivi") + g("bloc_touche"), g("sets_bloc")),
    }
    return d


def add(acc, row):
    for k in SUMCOLS:
        acc[k] = acc.get(k, 0) + (row.get(k) or 0)
    return acc


def fmt(v, kind):
    if v is None:
        return None
    if kind == "pct":
        return f"{math.floor(v * 100 + 0.5 + 1e-9)} %"
    if kind == "dec":   # arrondi « au plus proche, 0,5 vers le haut », comme le dashboard
        return f"{math.floor(v * 10 + 0.5 + 1e-9) / 10:.1f}".replace(".", ",")
    return str(v)


def fmt_ecart(a, b, kind):
    """écart entre deux valeurs : en points pour un pourcentage, en valeur pour un décimal."""
    if a is None or b is None:
        return None
    if kind == "pct":
        n = math.floor((a - b) * 100 + 0.5 + 1e-9)
        return f"{abs(n)} point" + ("s" if abs(n) > 1 else "")
    return f"{abs(a - b):.1f}".replace(".", ",")


def check_data(data):
    """Vérifie les sommes de contrôle (détecte une erreur de recopie des données)."""
    cs = data.get("checksum")
    if not cs:
        sys.exit("ERREUR : pas de somme de contrôle dans data.json")
    for k, expected in cs.items():
        if k.startswith("_"):
            continue
        got = sum((r.get(k) or 0) for r in data["agg"])
        if got != expected:
            sys.exit(f"ERREUR somme de contrôle : {k} = {got}, attendu {expected}. Les données ont été mal recopiées.")
    if cs.get("_lignes") is not None and len(data["agg"]) != cs["_lignes"]:
        sys.exit(f"ERREUR : {len(data['agg'])} lignes, attendu {cs['_lignes']}")


def build_facts(data, match_id):
    check_data(data)
    matchs = {m["match_id"]: m for m in data["matchs"]}
    if match_id not in matchs:
        sys.exit(f"ERREUR : match {match_id} introuvable")
    m = matchs[match_id]
    sets_par_match = {}
    for s in data["sets"]:
        sets_par_match.setdefault(s["match_id"], []).append(s)
    before = sorted(i for i in matchs if i < match_id)
    suivi_bloc = {r["match_id"] for r in data["agg"] if r.get("bloc_touche") is not None}

    def team_sums(ids):
        acc = {"sets": 0}
        for r in data["agg"]:
            if r["match_id"] in ids:
                add(acc, r)
        acc["sets"] = sum(len(sets_par_match.get(i, [])) for i in ids)
        acc["sets_bloc"] = sum(len(sets_par_match.get(i, [])) for i in ids if i in suivi_bloc)
        return acc

    def player_sums(name, ids):
        acc = {"sets": 0}
        for r in data["agg"]:
            if r["match_id"] in ids and r["joueur"] == name:
                add(acc, r)
                acc["sets"] += r.get("sets_joues") or 0
                acc["sets_bloc"] = acc.get("sets_bloc", 0) + (r.get("sets_bloc_suivi") or 0)
        return acc

    ids = {}          # {id: texte}
    facts = {"match": {}, "equipe": {}, "joueurs": {}, "evolution": {}}

    # --- match
    sc = sorted(sets_par_match.get(match_id, []), key=lambda s: s["set_no"])
    res = "victoire" if m["sets_equipe"] > m["sets_adv"] else "défaite"
    ids["match.adv"] = m["adversaire"]
    ids["match.score"] = f"{m['sets_equipe']}–{m['sets_adv']}"
    ids["match.sets_equipe"] = str(m["sets_equipe"])
    ids["match.sets_adv"] = str(m["sets_adv"])
    ids["match.resultat"] = res
    ids["match.scores_sets"] = ", ".join(f"{s['score_equipe']}–{s['score_adv']}" for s in sc)
    ids["saison.matchs_avant"] = str(len(before))
    ids["saison.matchs"] = str(len(before) + 1)
    facts["match"] = {"id": match_id, "adversaire": m["adversaire"], "date": str(m["date"])[:10], "resultat": res,
                      "sets_equipe": m["sets_equipe"], "sets_adv": m["sets_adv"], "nb_matchs_avant": len(before)}

    # --- équipe : ce match vs saison avant
    cur = derive(team_sums([match_id]))
    # totaux du match (points marqués : attaque + service + bloc ; fautes : attaque + service + autres)
    ids["eq.pts_total"], ids["eq.fautes_total"] = str(cur["pts_total"]), str(cur["fautes_total"])
    facts["match"]["points_marques"], facts["match"]["fautes"] = cur["pts_total"], cur["fautes_total"]
    prev = derive(team_sums(before)) if before else None
    for k, (label, kind, higher, _) in METRICS.items():
        v, p = cur[k], (prev[k] if prev else None)
        entry = {"label": label, "format": kind, "plus_haut_mieux": higher,
                 "match": v, "saison_avant": p}
        if v is not None:
            ids[f"eq.{k}.match"] = fmt(v, kind)
        if p is not None:
            ids[f"eq.{k}.saison"] = fmt(p, kind)
        if v is not None and p is not None:
            diff = v - p
            seuil = 0.02 if kind == "pct" else 0.2
            entry["tendance"] = "stable" if abs(diff) < seuil else ("mieux" if (diff > 0) == higher else "moins bien")
            ids[f"eq.{k}.ecart"] = fmt_ecart(v, p, kind)
        facts["equipe"][k] = entry
        # évolution match par match
        ev = {}
        for i in sorted(matchs):
            if i <= match_id:
                d = derive(team_sums([i]))
                if d[k] is not None:
                    ev[i] = d[k]
                    ids[f"eq.{k}.m{i}"] = fmt(d[k], kind)
        facts["evolution"][k] = ev

    # --- joueurs
    noms = sorted({r["joueur"] for r in data["agg"] if r["match_id"] == match_id})
    for n in noms:
        c = derive(player_sums(n, [match_id]))
        p = derive(player_sums(n, before)) if before else None
        # pas de poste : à notre niveau il n'a pas d'importance (et il prêtait à confusion)
        info = {"sets_match": c["sets"], "points_marques": c["pts_total"], "fautes": c["fautes_total"], "metriques": {}}
        ids[f"j.{n}.pts_total"], ids[f"j.{n}.fautes_total"] = str(c["pts_total"]), str(c["fautes_total"])
        for k, (label, kind, higher, (col, mini)) in METRICS.items():
            ok_match = (c[col] or 0) >= mini and c[k] is not None
            ok_prev = p is not None and (p[col] or 0) >= mini and p[k] is not None
            if not ok_match:
                continue
            e = {"label": label, "format": kind, "plus_haut_mieux": higher, "match": c[k], "echantillon": c[col]}
            ids[f"j.{n}.{k}.match"] = fmt(c[k], kind)
            if ok_prev:
                e["saison_avant"] = p[k]
                ids[f"j.{n}.{k}.saison"] = fmt(p[k], kind)
                ids[f"j.{n}.{k}.ecart"] = fmt_ecart(c[k], p[k], kind)
                diff = c[k] - p[k]
                seuil = 0.05 if kind == "pct" else 0.3
                e["tendance"] = "stable" if abs(diff) < seuil else ("mieux" if (diff > 0) == higher else "moins bien")
            info["metriques"][k] = e
        info["eligible"] = bool(info["metriques"]) and c["sets"] >= 2
        facts["joueurs"][n] = info

    facts["ids"] = ids
    facts["generated_for_match"] = match_id
    return facts


def add_classement(facts, cal):
    """Ajoute le classement officiel (fédération) : notre rang et celui de l'adversaire du match."""
    def ordinal(n):
        return "1er" if n == 1 else f"{n}e"
    cl = {c["equipe"]: c for c in cal.get("classement", [])}
    court = cal.get("noms_courts", {})
    nous = cl.get(cal.get("nous"))
    adv_nom = facts["match"]["adversaire"]
    off = cal.get("alias_base", {}).get(adv_nom) or next((n for n in cl if court.get(n, n).lower() == adv_nom.lower()), None)
    adv = cl.get(off) if off else None
    ids, info = facts["ids"], {"maj_le": cal.get("maj_le"), "nb_equipes": len(cl)}
    ids["classement.nb_equipes"] = str(len(cl))
    if nous:
        info["notre_rang"], info["nos_points"] = nous["rang"], nous["points"]
        ids["classement.notre_rang"] = ordinal(nous["rang"])
        ids["classement.nos_points"] = f"{nous['points']} point" + ("s" if nous["points"] > 1 else "")
    if adv:
        info["adv_rang"], info["adv_points"], info["adv_nom_officiel"] = adv["rang"], adv["points"], off
        ids["adv.rang"] = ordinal(adv["rang"])
        ids["adv.points"] = f"{adv['points']} point" + ("s" if adv["points"] > 1 else "")
    else:
        info["adv_rang"] = None
        print(f"Attention : adversaire « {adv_nom} » introuvable dans le classement (ajoute-le à alias_base)", file=sys.stderr)
    # prochain match (pour conclure le compte rendu)
    nxt = next((m for m in cal.get("matchs", []) if m.get("adversaire") and m.get("sets_nous") is None
                and m["date"] > facts["match"]["date"]), None)
    if nxt:
        info["prochain"] = {"date": nxt["date"], "lieu": nxt["lieu"], "adversaire": court.get(nxt["adversaire"], nxt["adversaire"]),
                            "rang": cl.get(nxt["adversaire"], {}).get("rang")}
        ids["prochain.adv"] = court.get(nxt["adversaire"], nxt["adversaire"])
        if info["prochain"]["rang"]:
            ids["prochain.rang"] = ordinal(info["prochain"]["rang"])
    facts["classement"] = info


# ----------------------------------------------------------------- contrôle et rendu
PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def check_text(text, facts, where, errors, player=None):
    if not isinstance(text, str) or not text.strip():
        errors.append(f"{where} : texte vide")
        return text
    ids = facts["ids"]
    stripped = PLACEHOLDER.sub(" ", text)
    mo = re.search(r".{0,15}\d.{0,15}", stripped)
    if mo:
        errors.append(f"{where} : chiffre écrit en dur (« {mo.group(0)} »). Utilise une référence {{{{id}}}}.")
    for w in BANNED:
        if re.search(rf"(?<!\w){w}(?!\w)", stripped, re.I):
            errors.append(f"{where} : formulation interdite ({w}). Reste positif, parle d'axe de progrès.")
    if len(text) > 400:
        errors.append(f"{where} : trop long ({len(text)} caractères, maximum 400)")
    for ref in PLACEHOLDER.findall(text):
        if ref not in ids:
            errors.append(f"{where} : référence inconnue ou sans assez d'actions : {{{{{ref}}}}}")
            continue
        if ref.startswith("j.") and player is not None and not ref.startswith(f"j.{player}."):
            errors.append(f"{where} : cite un autre joueur que {player} ({{{{{ref}}}}})")
    def sub(mo):
        return ids.get(mo.group(1).strip(), mo.group(0))
    return PLACEHOLDER.sub(sub, text)


def render(facts, report, index_path, dry_run=False):
    errors = []
    mid = facts["generated_for_match"]
    if report.get("match_id") != mid:
        errors.append(f"match_id du rapport ({report.get('match_id')}) différent de {mid}")
    out = {"match_id": mid, "adversaire": facts["match"]["adversaire"], "date": facts["match"]["date"],
           "genere_le": datetime.date.today().isoformat(), "masque": False}

    out["titre"] = check_text(report.get("titre"), facts, "titre", errors)
    for fld, lo, hi in (("equipe", 2, 4), ("points_forts", 1, 3), ("saison", 1, 3)):
        arr = report.get(fld)
        if not isinstance(arr, list) or not (lo <= len(arr) <= hi):
            errors.append(f"{fld} : attendu entre {lo} et {hi} phrases")
            continue
        out[fld] = [check_text(t, facts, f"{fld}[{i}]", errors) for i, t in enumerate(arr)]

    foc = report.get("focus") or {}
    out["focus"] = {}
    for k in ("titre", "pourquoi", "exercice"):
        out["focus"][k] = check_text(foc.get(k), facts, f"focus.{k}", errors)

    out["joueurs"] = []
    vus = set()
    for j in report.get("joueurs") or []:
        n = j.get("joueur")
        info = facts["joueurs"].get(n)
        if not info or not info["eligible"]:
            errors.append(f"joueurs : {n} n'a pas assez d'actions dans ce match pour être commenté")
            continue
        if n in vus:
            errors.append(f"joueurs : {n} apparaît deux fois")
        vus.add(n)
        sp = j.get("super_pouvoir")
        if not isinstance(sp, str) or not sp.strip():
            errors.append(f"joueurs.{n}.super_pouvoir : manquant (un titre court, par exemple « Le mur au filet »)")
        else:
            sp = sp.strip()
            if PLACEHOLDER.search(sp) or re.search(r"\d", sp):
                errors.append(f"joueurs.{n}.super_pouvoir : pas de chiffre ni de référence dans le titre (« {sp} »)")
            if len(sp) > 40:
                errors.append(f"joueurs.{n}.super_pouvoir : trop long ({len(sp)} caractères, maximum 40)")
            for w in BANNED:
                if re.search(rf"(?<!\w){w}(?!\w)", sp, re.I):
                    errors.append(f"joueurs.{n}.super_pouvoir : formulation interdite ({w})")
        out["joueurs"].append({
            "joueur": n,
            "super_pouvoir": sp,
            "point_fort": check_text(j.get("point_fort"), facts, f"joueurs.{n}.point_fort", errors, player=n),
            "axe": check_text(j.get("axe"), facts, f"joueurs.{n}.axe", errors, player=n)})
    manquants = [n for n, i in facts["joueurs"].items() if i["eligible"] and n not in vus]
    if manquants:
        errors.append("joueurs : il manque " + ", ".join(manquants))

    if errors:
        print("REFUSÉ :", file=sys.stderr)
        for e in errors:
            print(" -", e, file=sys.stderr)
        sys.exit(2)

    if dry_run:
        print("BROUILLON VALIDÉ (rien n'est écrit)\n")
        print(out["titre"] + "\n")
        for t in out["equipe"]:
            print(t)
        print("\nCe qui a bien marché :")
        for t in out["points_forts"]:
            print(" -", t)
        print("\nFocus du prochain entraînement : " + out["focus"]["titre"])
        print(" Pourquoi :", out["focus"]["pourquoi"])
        print(" Au programme :", out["focus"]["exercice"])
        print("\nDepuis le début de la saison :")
        for t in out["saison"]:
            print(" -", t)
        print("\nUn mot pour chacun :")
        for j in out["joueurs"]:
            print(f" {j['joueur']} : 🦸 « {j.get('super_pouvoir')} » {j['point_fort']}  🎯 Son défi : {j['axe']}")
        return
    try:
        idx = json.load(open(index_path, encoding="utf-8"))
    except FileNotFoundError:
        idx = {"version": 1, "analyses": []}
    idx["analyses"] = [a for a in idx["analyses"] if a["match_id"] != mid] + [out]
    idx["analyses"].sort(key=lambda a: a["match_id"])
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    print(f"OK : compte rendu du match {mid} écrit dans {index_path} ({len(out['joueurs'])} joueurs commentés)")


def todo(data, index_path):
    try:
        idx = json.load(open(index_path, encoding="utf-8"))
    except FileNotFoundError:
        idx = {}
    done = {a["match_id"] for a in idx.get("analyses", [])}
    depuis = idx.get("a_partir_du_match", 1)
    manque = sorted(m["match_id"] for m in data["matchs"] if m["match_id"] >= depuis and m["match_id"] not in done and
                    any(s["match_id"] == m["match_id"] for s in data["sets"]))
    print(json.dumps(manque))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("facts"); a.add_argument("data"); a.add_argument("--match", type=int, required=True); a.add_argument("--out", default="facts.json"); a.add_argument("--calendrier", default=None, help="calendrier/ffvb.json (classement officiel)")
    b = sub.add_parser("render"); b.add_argument("facts"); b.add_argument("report"); b.add_argument("--index", required=True); b.add_argument("--dry-run", action="store_true")
    c = sub.add_parser("todo"); c.add_argument("data"); c.add_argument("index")
    args = ap.parse_args()
    if args.cmd == "facts":
        facts = build_facts(json.load(open(args.data, encoding="utf-8")), args.match)
        if args.calendrier:
            add_classement(facts, json.load(open(args.calendrier, encoding="utf-8")))
        json.dump(facts, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"OK : faits du match {args.match} dans {args.out}")
        print("Joueurs commentables :", ", ".join(n for n, i in facts["joueurs"].items() if i["eligible"]) or "aucun")
    elif args.cmd == "render":
        render(json.load(open(args.facts, encoding="utf-8")), json.load(open(args.report, encoding="utf-8")), args.index, args.dry_run)
    else:
        todo(json.load(open(args.data, encoding="utf-8")), args.index)


if __name__ == "__main__":
    main()
