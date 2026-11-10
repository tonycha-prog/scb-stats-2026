-- Étape 1 du plan d'optimisation (à coller une fois dans Supabase > SQL Editor > Run)
-- 1) Archive automatique : avant qu'un match soit supprimé ou remplacé (renvoi depuis l'app),
--    une copie complète (match, sets, stats) est rangée dans private.archive_matchs.
-- 2) Le poste devient facultatif (il n'est plus utilisé nulle part).

create table if not exists private.archive_matchs (
  version_id bigint generated always as identity primary key,
  match_id integer not null,
  archive_le timestamptz not null default now(),
  match jsonb not null,
  sets jsonb,
  stats jsonb
);
alter table private.archive_matchs enable row level security;
comment on table private.archive_matchs is 'Copie d''un match faite automatiquement juste avant qu''il soit supprimé ou remplacé.';

create or replace function private.archiver_match()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into private.archive_matchs (match_id, match, sets, stats)
  values (
    old.match_id,
    to_jsonb(old),
    (select jsonb_agg(to_jsonb(s) order by s.set_no) from public.sets s where s.match_id = old.match_id),
    (select jsonb_agg(to_jsonb(p) order by p.set_no, p.joueur) from public.stats_par_set p where p.match_id = old.match_id)
  );
  return old;
end;
$$;
revoke all on function private.archiver_match() from public, anon, authenticated;

drop trigger if exists archiver_avant_suppression on public.matchs;
create trigger archiver_avant_suppression
  before delete on public.matchs
  for each row execute function private.archiver_match();

alter table public.stats_par_set alter column poste drop not null;
