-- Données agrégées par match et par joueur, avec sommes de contrôle (résultat : une seule colonne data_json, un objet JSON)
with agg as (
  select match_id, joueur, max(poste) as poste, count(*)::int as sets_joues,
    sum(serv_nb)::int as serv_nb,
    sum(serv_aces)::int as serv_aces,
    sum(serv_adv_diff)::int as serv_adv_diff,
    sum(serv_fautes)::int as serv_fautes,
    sum(serv_neutres)::int as serv_neutres,
    sum(att_nb)::int as att_nb,
    sum(att_points)::int as att_points,
    sum(att_adv_diff)::int as att_adv_diff,
    sum(att_fautes)::int as att_fautes,
    sum(att_bloquees)::int as att_bloquees,
    sum(point_bloc)::int as point_bloc,
    sum(rec_plus_passeur)::int as rec_plus_passeur,
    sum(rec_moy_tmoy)::int as rec_moy_tmoy,
    sum(rec_moins_manquee)::int as rec_moins_manquee,
    sum(def_ok_passeur)::int as def_ok_passeur,
    sum(def_tmoy)::int as def_tmoy,
    sum(def_moins_manquee)::int as def_moins_manquee,
    sum(rel_plus_passeur)::int as rel_plus_passeur,
    sum(rel_moy)::int as rel_moy,
    sum(autres_fautes)::int as autres_fautes
  from public.stats_par_set
  group by match_id, joueur
)
select json_build_object(
  'matchs', (select json_agg(m order by m.match_id) from (select match_id, date::text as date, adversaire, sets_equipe, sets_adv from public.matchs) m),
  'sets',   (select json_agg(s order by s.match_id, s.set_no) from (select match_id, set_no, resultat, score_equipe, score_adv from public.sets) s),
  'agg',    (select json_agg(a order by a.match_id, a.joueur) from agg a),
  'checksum', (select json_build_object(
    'serv_nb', sum(serv_nb),
    'serv_aces', sum(serv_aces),
    'serv_adv_diff', sum(serv_adv_diff),
    'serv_fautes', sum(serv_fautes),
    'serv_neutres', sum(serv_neutres),
    'att_nb', sum(att_nb),
    'att_points', sum(att_points),
    'att_adv_diff', sum(att_adv_diff),
    'att_fautes', sum(att_fautes),
    'att_bloquees', sum(att_bloquees),
    'point_bloc', sum(point_bloc),
    'rec_plus_passeur', sum(rec_plus_passeur),
    'rec_moy_tmoy', sum(rec_moy_tmoy),
    'rec_moins_manquee', sum(rec_moins_manquee),
    'def_ok_passeur', sum(def_ok_passeur),
    'def_tmoy', sum(def_tmoy),
    'def_moins_manquee', sum(def_moins_manquee),
    'rel_plus_passeur', sum(rel_plus_passeur),
    'rel_moy', sum(rel_moy),
    'autres_fautes', sum(autres_fautes),
    'sets_joues', sum(sets_joues), '_lignes', count(*)) from agg)
) as data_json;
