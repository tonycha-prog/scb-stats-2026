/**
 * SCB – réception des stats envoyées par la page de saisie.
 * À coller dans Extensions > Apps Script du Google Sheet de l'équipe.
 * 1) Remplace CODE_SECRET par un mot de passe de ton choix.
 * 2) Déployer > Nouveau déploiement > Application web
 *    Exécuter en tant que : Moi  |  Qui a accès : Tout le monde
 * 3) Copie l'URL « …/exec » et colle-la, avec le code, dans Réglages de la page de saisie.
 *
 * Onglets utilisés (créés s'ils n'existent pas) : match, sets, stats_par_set.
 * Un renvoi du même match remplace ses lignes (jamais de doublon).
 */
const CODE_SECRET = "CODE_SECRET";

const HEADERS = {
  match: ["match_id","date","equipe","adversaire","lieu","sets_equipe","sets_adv"],
  sets: ["match_id","set_no","resultat","score_equipe","score_adv"],
  stats_par_set: ["match_id","set_no","joueur_id","joueur","poste",
    "serv_nb","serv_aces","serv_adv_diff","serv_fautes","serv_neutres",
    "att_nb","att_points","att_adv_diff","att_fautes","att_bloquees","point_bloc",
    "rec_plus_passeur","rec_moy_tmoy","rec_moins_manquee",
    "def_ok_passeur","def_tmoy","def_moins_manquee","rel_plus_passeur","rel_moy","autres_fautes"]
};

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    const d = JSON.parse(e.postData.contents);
    if (d.token !== CODE_SECRET) return out({ ok: false, error: "Code secret incorrect" });
    if (!d.match || !d.sets || !d.stats) return out({ ok: false, error: "Données incomplètes" });

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const id = Number(d.match.match_id);

    // Sécurité : ne pas écraser un autre match qui aurait le même numéro
    const sm = sheetFor(ss, "match");
    const existing = readRows(sm).find(r => Number(r.match_id) === id);
    if (existing && String(existing.adversaire).trim().toLowerCase() !== String(d.match.adversaire).trim().toLowerCase()) {
      return out({ ok: false, error: "Le match n°" + id + " existe déjà pour « " + existing.adversaire + " ». Change le n° du match." });
    }

    replace(ss, "match", [d.match], id);
    replace(ss, "sets", d.sets, id);
    replace(ss, "stats_par_set", d.stats, id);
    return out({ ok: true, match_id: id, stats_rows: d.stats.length });
  } catch (err) {
    return out({ ok: false, error: String(err && err.message || err) });
  } finally {
    try { lock.releaseLock(); } catch (x) {}
  }
}

function doGet() { return out({ ok: true, info: "SCB saisie : l'application web répond." }); }

function out(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function sheetFor(ss, name) {
  let sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, HEADERS[name].length).setValues([HEADERS[name]]);
    sh.setFrozenRows(1);
  }
  return sh;
}

function readRows(sh) {
  const v = sh.getDataRange().getValues();
  if (v.length < 2) return [];
  const h = v[0];
  return v.slice(1).map(r => { const o = {}; h.forEach((k, i) => o[k] = r[i]); return o; });
}

function replace(ss, name, rows, matchId) {
  const sh = sheetFor(ss, name);
  const head = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  const col = head.indexOf("match_id");
  // supprimer les anciennes lignes de ce match (de bas en haut)
  const data = sh.getDataRange().getValues();
  for (let i = data.length - 1; i >= 1; i--) {
    if (Number(data[i][col]) === matchId) sh.deleteRow(i + 1);
  }
  if (!rows.length) return;
  const values = rows.map(r => head.map(h => (r[h] === undefined || r[h] === null) ? "" : r[h]));
  sh.getRange(sh.getLastRow() + 1, 1, values.length, head.length).setValues(values);
}
