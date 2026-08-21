-- Expose stale optimistic-concurrency writes as a deterministic PostgREST 409.
-- PT409 is an application conflict, not a retryable PostgreSQL transaction error.

create or replace function public.apply_revisioned_update()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  owner_column text := tg_argv[0];
  key_column text := tg_argv[1];
begin
  if new.id <> old.id then
    raise exception using errcode = '22023', message = 'id is immutable';
  end if;
  if (to_jsonb(new) ->> owner_column) is distinct from (to_jsonb(old) ->> owner_column) then
    raise exception using errcode = '22023', message = owner_column || ' is immutable';
  end if;
  if key_column <> '' and (to_jsonb(new) ->> key_column) is distinct from (to_jsonb(old) ->> key_column) then
    raise exception using errcode = '22023', message = key_column || ' is immutable';
  end if;
  if new.last_mutation_id = old.last_mutation_id then
    return old;
  end if;
  if new.revision <> old.revision then
    raise sqlstate 'PT409'
      using
        message = 'revision conflict',
        detail = format(
          'expected revision %s, received %s',
          old.revision,
          new.revision
        ),
        hint = 'Reload remote state and resolve the conflict before retrying';
  end if;
  new.created_at := old.created_at;
  new.revision := old.revision + 1;
  new.server_updated_at := statement_timestamp();
  return new;
end;
$$;
