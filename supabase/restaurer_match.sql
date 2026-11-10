-- Restaurer une ancienne version d'un match depuis l'archive.
-- 1) Voir les versions archivées d'un match (remplacer 3 par le n° du match) :
--    select version_id, match_id, archive_le, match->>'adversaire' as adversaire, match->>'date' as date,
--           jsonb_array_length(stats) as lignes
--    from private.archive_matchs where match_id = 3 order by archive_le desc;
-- 2) Restaurer la version choisie (remplacer 12 par le version_id). La version actuelle est elle-même
--    archivée automatiquement au passage, donc on peut toujours revenir en arrière.
do $$
declare v private.archive_matchs;
begin
  select * into v from private.archive_matchs where version_id = 12;
  if v is null then raise exception 'Version introuvable'; end if;
  delete from public.matchs where match_id = v.match_id;
  insert into public.matchs select * from jsonb_populate_record(null::public.matchs, v.match);
  insert into public.sets select * from jsonb_populate_recordset(null::public.sets, v.sets);
  insert into public.stats_par_set select * from jsonb_populate_recordset(null::public.stats_par_set, v.stats);
end $$;
