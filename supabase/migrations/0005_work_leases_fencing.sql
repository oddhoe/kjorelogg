-- FASE 5.9: dataset-scoped work lease, fencing, client gate and audit.
-- Requires 0004_dataset_membership.sql.

create table public.work_leases (
  id uuid primary key default gen_random_uuid(),
  dataset_id uuid not null references public.datasets(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  device_id text not null,
  session_id uuid not null,
  acquired_at timestamptz not null default statement_timestamp(),
  last_heartbeat_at timestamptz not null default statement_timestamp(),
  expires_at timestamptz not null,
  fencing_generation bigint not null,
  released_at timestamptz,
  server_updated_at timestamptz not null default statement_timestamp(),
  constraint work_leases_device_not_blank check (length(btrim(device_id)) between 1 and 200),
  constraint work_leases_generation_positive check (fencing_generation > 0),
  constraint work_leases_expiry_after_acquire check (expires_at > acquired_at),
  constraint work_leases_user_device_fk foreign key (user_id, device_id)
    references public.devices(user_id, device_id)
);

create unique index work_leases_one_active_dataset_idx
  on public.work_leases (dataset_id) where released_at is null;
create unique index work_leases_generation_idx
  on public.work_leases (dataset_id, fencing_generation);
create index work_leases_owner_idx
  on public.work_leases (user_id, server_updated_at desc);

create table public.sync_runtime_config (
  singleton boolean primary key default true check (singleton),
  minimum_write_client_version text not null,
  lease_ttl_seconds integer not null default 900,
  takeover_grace_seconds integer not null default 300,
  heartbeat_seconds integer not null default 120,
  server_updated_at timestamptz not null default statement_timestamp(),
  constraint sync_runtime_config_version check (minimum_write_client_version ~ '^v[0-9]+\.[0-9]+\.[0-9]+$'),
  constraint sync_runtime_config_ttl check (lease_ttl_seconds between 60 and 86400),
  constraint sync_runtime_config_grace check (takeover_grace_seconds between 0 and 86400),
  constraint sync_runtime_config_heartbeat check (heartbeat_seconds between 30 and 3600)
);

insert into public.sync_runtime_config
  (singleton, minimum_write_client_version, lease_ttl_seconds,
   takeover_grace_seconds, heartbeat_seconds)
values (true, 'v2.0.105', 900, 300, 120)
on conflict (singleton) do nothing;

create table public.sync_audit_log (
  id bigint generated always as identity primary key,
  dataset_id uuid not null references public.datasets(id) on delete restrict,
  entity_type text not null,
  entity_id uuid not null,
  entity_key text,
  user_id uuid not null references auth.users(id) on delete restrict,
  device_id text,
  session_id uuid not null,
  mutation_id uuid not null,
  previous_revision bigint,
  new_revision bigint not null,
  old_status text,
  new_status text,
  fencing_generation bigint not null,
  client_version text not null,
  server_created_at timestamptz not null default statement_timestamp()
);

create unique index sync_audit_mutation_idx
  on public.sync_audit_log (dataset_id, entity_type, mutation_id);
create index sync_audit_dataset_time_idx
  on public.sync_audit_log (dataset_id, server_created_at desc);

alter table public.work_leases enable row level security;
alter table public.sync_runtime_config enable row level security;
alter table public.sync_audit_log enable row level security;

create policy work_leases_select_member on public.work_leases
  for select to authenticated using (public.is_dataset_member(dataset_id, false));
create policy sync_runtime_config_select_authenticated on public.sync_runtime_config
  for select to authenticated using (true);
create policy sync_audit_select_member on public.sync_audit_log
  for select to authenticated using (public.is_dataset_member(dataset_id, false));

revoke all on public.work_leases from anon, authenticated;
revoke all on public.sync_runtime_config from anon, authenticated;
revoke all on public.sync_audit_log from anon, authenticated;
grant select on public.work_leases to authenticated;
grant select on public.sync_runtime_config to authenticated;
grant select on public.sync_audit_log to authenticated;

alter table public.road_progress
  add column work_session_id uuid,
  add column fencing_generation bigint,
  add column client_version text,
  add column deleted_by uuid references auth.users(id) on delete set null;
alter table public.measurement_tracks
  add column work_session_id uuid,
  add column fencing_generation bigint,
  add column client_version text,
  add column deleted_by uuid references auth.users(id) on delete set null;
alter table public.asphalt_plans
  add column work_session_id uuid,
  add column fencing_generation bigint,
  add column client_version text,
  add column deleted_by uuid references auth.users(id) on delete set null;
alter table public.asphalt_progress
  add column work_session_id uuid,
  add column fencing_generation bigint,
  add column client_version text,
  add column deleted_by uuid references auth.users(id) on delete set null;
alter table public.app_settings
  add column work_session_id uuid,
  add column fencing_generation bigint,
  add column client_version text,
  add column deleted_by uuid references auth.users(id) on delete set null;
alter table public.day_plans
  add column work_session_id uuid,
  add column fencing_generation bigint,
  add column client_version text,
  add column deleted_by uuid references auth.users(id) on delete set null;

create or replace function public.acquire_work_lease(
  p_dataset_id uuid,
  p_device_id text,
  p_session_id uuid
)
returns public.work_leases
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_now timestamptz := statement_timestamp();
  v_ttl integer;
  v_grace integer;
  v_current public.work_leases;
  v_generation bigint;
  v_result public.work_leases;
begin
  if v_user is null then
    raise sqlstate 'PT401' using message = 'authentication required';
  end if;
  if not public.is_dataset_member(p_dataset_id, true) then
    raise sqlstate 'PT403' using message = 'active driver membership required';
  end if;
  if not exists (
    select 1 from public.devices d
    where d.user_id = v_user and d.device_id = p_device_id
  ) then
    raise sqlstate 'PT409' using message = 'device is not registered';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_dataset_id::text, 0));
  select lease_ttl_seconds, takeover_grace_seconds into v_ttl, v_grace
    from public.sync_runtime_config where singleton;
  select * into v_current from public.work_leases
    where dataset_id = p_dataset_id and released_at is null
    for update;

  if found and v_current.user_id = v_user
     and v_current.device_id = p_device_id
     and v_current.session_id = p_session_id
     and v_current.expires_at > v_now then
    update public.work_leases set
      last_heartbeat_at = v_now,
      expires_at = v_now + make_interval(secs => v_ttl),
      server_updated_at = v_now
    where id = v_current.id returning * into v_result;
    return v_result;
  end if;

  if found and v_current.expires_at + make_interval(secs => v_grace) > v_now then
    raise sqlstate 'PT423'
      using message = 'dataset is leased by another work session',
            hint = 'Wait for expiry and grace; takeover is never automatic while protected';
  end if;

  if found then
    update public.work_leases set released_at = v_now, server_updated_at = v_now
      where id = v_current.id;
  end if;
  select coalesce(max(fencing_generation), 0) + 1 into v_generation
    from public.work_leases where dataset_id = p_dataset_id;
  insert into public.work_leases
    (dataset_id, user_id, device_id, session_id, acquired_at,
     last_heartbeat_at, expires_at, fencing_generation, server_updated_at)
  values
    (p_dataset_id, v_user, p_device_id, p_session_id, v_now,
     v_now + interval '0 seconds', v_now + make_interval(secs => v_ttl),
     v_generation, v_now)
  returning * into v_result;
  return v_result;
end;
$$;

create or replace function public.renew_work_lease(
  p_lease_id uuid,
  p_session_id uuid,
  p_fencing_generation bigint
)
returns public.work_leases
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_now timestamptz := statement_timestamp();
  v_ttl integer;
  v_result public.work_leases;
begin
  select lease_ttl_seconds into v_ttl from public.sync_runtime_config where singleton;
  update public.work_leases set
    last_heartbeat_at = v_now,
    expires_at = v_now + make_interval(secs => v_ttl),
    server_updated_at = v_now
  where id = p_lease_id
    and user_id = auth.uid()
    and session_id = p_session_id
    and fencing_generation = p_fencing_generation
    and released_at is null
    and expires_at > v_now
    and public.is_dataset_member(dataset_id, true)
  returning * into v_result;
  if not found then
    raise sqlstate 'PT412' using message = 'lease is stale or expired';
  end if;
  return v_result;
end;
$$;

create or replace function public.release_work_lease(
  p_lease_id uuid,
  p_session_id uuid,
  p_fencing_generation bigint
)
returns public.work_leases
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_result public.work_leases;
begin
  update public.work_leases set
    released_at = statement_timestamp(),
    server_updated_at = statement_timestamp()
  where id = p_lease_id
    and user_id = auth.uid()
    and session_id = p_session_id
    and fencing_generation = p_fencing_generation
    and released_at is null
  returning * into v_result;
  if not found then
    raise sqlstate 'PT412' using message = 'lease is stale or already released';
  end if;
  return v_result;
end;
$$;

create or replace function public.kjorelogg_semver_code(p_version text)
returns numeric
language plpgsql
immutable
set search_path = ''
as $$
declare
  v text := substring(coalesce(p_version, '') from 2);
begin
  if coalesce(p_version, '') !~ '^v[0-9]+\.[0-9]+\.[0-9]+$' then
    return -1;
  end if;
  return split_part(v, '.', 1)::numeric * 1000000000000
       + split_part(v, '.', 2)::numeric * 1000000
       + split_part(v, '.', 3)::numeric;
end;
$$;

-- Identical mutation retry is admitted even after lease loss; the existing
-- revision trigger returns OLD, so no second effect or revision increment occurs.
create or replace function public.validate_dataset_fence()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_owner_column text := tg_argv[0];
  v_minimum_version text;
begin
  if tg_op = 'UPDATE' and new.last_mutation_id = old.last_mutation_id then
    return new;
  end if;
  if tg_op = 'UPDATE' and new.dataset_id is distinct from old.dataset_id then
    raise sqlstate '22023' using message = 'dataset_id is immutable';
  end if;
  if new.dataset_id is null then
    raise sqlstate 'PT412' using message = 'dataset_id is required for synchronized writes';
  end if;
  if new.work_session_id is null or new.fencing_generation is null
     or new.updated_device_id is null or btrim(new.updated_device_id) = '' then
    raise sqlstate 'PT412' using message = 'active work lease is required';
  end if;
  if not public.is_dataset_member(new.dataset_id, true) then
    raise sqlstate 'PT403' using message = 'active driver membership required';
  end if;
  select minimum_write_client_version into v_minimum_version
    from public.sync_runtime_config where singleton;
  if public.kjorelogg_semver_code(new.client_version)
     < public.kjorelogg_semver_code(v_minimum_version) then
    raise sqlstate 'PT426'
      using message = 'minimum write client version required',
            detail = 'minimum version is ' || v_minimum_version;
  end if;
  if not exists (
    select 1 from public.work_leases l
    where l.dataset_id = new.dataset_id
      and l.user_id = auth.uid()
      and l.device_id = new.updated_device_id
      and l.session_id = new.work_session_id
      and l.fencing_generation = new.fencing_generation
      and l.released_at is null
      and l.expires_at > statement_timestamp()
  ) then
    raise sqlstate 'PT412' using message = 'stale fencing generation';
  end if;
  if tg_op = 'INSERT' then
    new := jsonb_populate_record(new, jsonb_build_object(v_owner_column, auth.uid()));
    new.device_id := new.updated_device_id;
    new.created_by := auth.uid();
  else
    new := jsonb_populate_record(new, jsonb_build_object(
      v_owner_column, to_jsonb(old) ->> v_owner_column
    ));
    new.device_id := old.device_id;
    new.created_by := old.created_by;
  end if;
  new.updated_by := auth.uid();
  if new.deleted_at is not null
     and (tg_op = 'INSERT' or old.deleted_at is distinct from new.deleted_at) then
    new.deleted_by := auth.uid();
  elsif tg_op = 'UPDATE' and new.deleted_at is null then
    new.deleted_by := null;
  end if;
  return new;
end;
$$;

create or replace function public.append_dataset_sync_audit()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_key_column text := tg_argv[0];
  v_key text := case when v_key_column = '' then null else to_jsonb(new) ->> v_key_column end;
begin
  insert into public.sync_audit_log
    (dataset_id, entity_type, entity_id, entity_key, user_id, device_id,
     session_id, mutation_id, previous_revision, new_revision, old_status,
     new_status, fencing_generation, client_version, server_created_at)
  values
    (new.dataset_id, tg_table_name, new.id, v_key, auth.uid(), new.updated_device_id,
     new.work_session_id, new.last_mutation_id,
     case when tg_op = 'UPDATE' then old.revision else null end,
     new.revision,
     case when tg_op = 'UPDATE' then to_jsonb(old) ->> 'status' else null end,
     to_jsonb(new) ->> 'status', new.fencing_generation, new.client_version,
     statement_timestamp())
  on conflict (dataset_id, entity_type, mutation_id) do nothing;
  return new;
end;
$$;

create trigger road_progress_00_fence before insert or update on public.road_progress
for each row execute function public.validate_dataset_fence('user_id');
create trigger measurement_tracks_00_fence before insert or update on public.measurement_tracks
for each row execute function public.validate_dataset_fence('user_id');
create trigger asphalt_plans_00_fence before insert or update on public.asphalt_plans
for each row execute function public.validate_dataset_fence('owner_user_id');
create trigger asphalt_progress_00_fence before insert or update on public.asphalt_progress
for each row execute function public.validate_dataset_fence('user_id');
create trigger app_settings_00_fence before insert or update on public.app_settings
for each row execute function public.validate_dataset_fence('user_id');
create trigger day_plans_00_fence before insert or update on public.day_plans
for each row execute function public.validate_dataset_fence('user_id');

create trigger road_progress_zz_audit after insert or update on public.road_progress
for each row execute function public.append_dataset_sync_audit('road_key');
create trigger measurement_tracks_zz_audit after insert or update on public.measurement_tracks
for each row execute function public.append_dataset_sync_audit('road_key');
create trigger asphalt_plans_zz_audit after insert or update on public.asphalt_plans
for each row execute function public.append_dataset_sync_audit('plan_key');
create trigger asphalt_progress_zz_audit after insert or update on public.asphalt_progress
for each row execute function public.append_dataset_sync_audit('plan_id');
create trigger app_settings_zz_audit after insert or update on public.app_settings
for each row execute function public.append_dataset_sync_audit('setting_key');
create trigger day_plans_zz_audit after insert or update on public.day_plans
for each row execute function public.append_dataset_sync_audit('plan_date');

revoke all on function public.acquire_work_lease(uuid, text, uuid) from public, anon;
revoke all on function public.renew_work_lease(uuid, uuid, bigint) from public, anon;
revoke all on function public.release_work_lease(uuid, uuid, bigint) from public, anon;
grant execute on function public.acquire_work_lease(uuid, text, uuid) to authenticated;
grant execute on function public.renew_work_lease(uuid, uuid, bigint) to authenticated;
grant execute on function public.release_work_lease(uuid, uuid, bigint) to authenticated;
revoke all on function public.validate_dataset_fence() from public, anon, authenticated;
revoke all on function public.append_dataset_sync_audit() from public, anon, authenticated;
revoke all on function public.kjorelogg_semver_code(text) from public, anon, authenticated;
