-- Kjørelogg initial Supabase schema.
-- User-generated data only; NVDB geometry/caches remain client-local.

create extension if not exists pgcrypto;

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  initials text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_display_name_length check (display_name is null or char_length(display_name) <= 120),
  constraint profiles_initials_length check (initials is null or char_length(initials) <= 16)
);

create table public.devices (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  device_id text not null,
  device_name text,
  platform text,
  app_version text,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  constraint devices_user_device_unique unique (user_id, device_id),
  constraint devices_device_id_not_blank check (length(btrim(device_id)) between 1 and 200)
);

create table public.road_progress (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  road_key text not null,
  road_key_version smallint not null default 1,
  county_id text,
  road_category text,
  road_number integer,
  segment text,
  status text not null,
  direction_fwd boolean not null default false,
  direction_rev boolean not null default false,
  manual_full boolean not null default false,
  single_direction boolean not null default false,
  measured_at timestamptz,
  operator text,
  vehicle text,
  comment text,
  length_km double precision,
  client_updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  device_id text,
  last_mutation_id uuid not null,
  revision bigint not null default 1,
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  constraint road_progress_user_road_unique unique (user_id, road_key),
  constraint road_progress_mutation_unique unique (user_id, last_mutation_id),
  constraint road_progress_road_key_not_blank check (length(btrim(road_key)) between 1 and 500),
  constraint road_progress_key_version_positive check (road_key_version > 0),
  constraint road_progress_category check (road_category is null or road_category in ('E', 'R', 'F', 'K', 'ASPHALT')),
  constraint road_progress_status check (status in ('NOT_STARTED', 'ONE_DIRECTION', 'COMPLETED', 'SKIPPED')),
  constraint road_progress_direction_consistency check (
    (status = 'NOT_STARTED' and not direction_fwd and not direction_rev and not manual_full)
    or (status = 'ONE_DIRECTION' and (direction_fwd or direction_rev) and not manual_full)
    or (status = 'COMPLETED' and (direction_fwd or direction_rev or manual_full))
    or (status = 'SKIPPED' and not direction_fwd and not direction_rev and not manual_full)
  ),
  constraint road_progress_manual_full_completed check (not manual_full or status = 'COMPLETED'),
  constraint road_progress_length_nonnegative check (length_km is null or length_km >= 0),
  constraint road_progress_revision_positive check (revision >= 1),
  constraint road_progress_device_fk foreign key (user_id, device_id)
    references public.devices(user_id, device_id)
);

create table public.measurement_tracks (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  road_key text not null,
  session_id uuid not null,
  direction text not null,
  started_at timestamptz not null,
  ended_at timestamptz not null,
  device_id text,
  point_count integer not null,
  encoding text not null default 'google_polyline6',
  encoded_track text not null,
  last_mutation_id uuid not null,
  client_updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  revision bigint not null default 1,
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  constraint measurement_tracks_direction check (direction in ('fwd', 'rev')),
  constraint measurement_tracks_time_order check (ended_at >= started_at),
  constraint measurement_tracks_point_count check (point_count >= 2),
  constraint measurement_tracks_encoding check (encoding in ('google_polyline5', 'google_polyline6')),
  constraint measurement_tracks_revision_positive check (revision >= 1),
  constraint measurement_tracks_mutation_unique unique (user_id, last_mutation_id),
  constraint measurement_tracks_user_session_direction_unique unique (user_id, session_id, road_key, direction),
  constraint measurement_tracks_device_fk foreign key (user_id, device_id)
    references public.devices(user_id, device_id)
);

create table public.asphalt_plans (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  plan_key text not null,
  plan_key_version smallint not null default 1,
  plan_year integer not null,
  county_id text not null,
  source_name text,
  road_category text not null default 'F',
  road_number integer not null,
  from_s integer not null,
  from_d integer not null,
  from_m double precision not null,
  to_s integer not null,
  to_d integer not null,
  to_m double precision not null,
  road_name text,
  contract text,
  planned_length_km double precision,
  asphalt_date date,
  asphalt_date_to date,
  client_updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  device_id text,
  last_mutation_id uuid not null,
  revision bigint not null default 1,
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  constraint asphalt_plans_owner_key_unique unique (owner_user_id, plan_key),
  constraint asphalt_plans_mutation_unique unique (owner_user_id, last_mutation_id),
  constraint asphalt_plans_key_not_blank check (length(btrim(plan_key)) between 1 and 500),
  constraint asphalt_plans_key_version_positive check (plan_key_version > 0),
  constraint asphalt_plans_year check (plan_year between 2000 and 2200),
  constraint asphalt_plans_category check (road_category in ('E', 'R', 'F', 'K')),
  constraint asphalt_plans_road_number check (road_number > 0),
  constraint asphalt_plans_references check (
    from_s >= 0 and from_d >= 0 and from_m >= 0 and
    to_s >= 0 and to_d >= 0 and to_m >= 0
  ),
  constraint asphalt_plans_length_nonnegative check (planned_length_km is null or planned_length_km >= 0),
  constraint asphalt_plans_dates_order check (asphalt_date_to is null or asphalt_date is null or asphalt_date_to >= asphalt_date),
  constraint asphalt_plans_revision_positive check (revision >= 1),
  constraint asphalt_plans_device_fk foreign key (owner_user_id, device_id)
    references public.devices(user_id, device_id)
);

create table public.asphalt_progress (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan_id uuid not null references public.asphalt_plans(id) on delete cascade,
  status text not null,
  direction_fwd boolean not null default false,
  direction_rev boolean not null default false,
  manual_full boolean not null default false,
  comment text,
  measured_at timestamptz,
  completed_at timestamptz,
  operator text,
  vehicle text,
  device_id text,
  client_updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  last_mutation_id uuid not null,
  revision bigint not null default 1,
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  constraint asphalt_progress_user_plan_unique unique (user_id, plan_id),
  constraint asphalt_progress_mutation_unique unique (user_id, last_mutation_id),
  constraint asphalt_progress_status check (status in ('NOT_STARTED', 'ONE_DIRECTION', 'COMPLETED', 'SKIPPED')),
  constraint asphalt_progress_direction_consistency check (
    (status = 'NOT_STARTED' and not direction_fwd and not direction_rev and not manual_full)
    or (status = 'ONE_DIRECTION' and (direction_fwd or direction_rev) and not manual_full)
    or (status = 'COMPLETED' and (direction_fwd or direction_rev or manual_full))
    or (status = 'SKIPPED' and not direction_fwd and not direction_rev and not manual_full)
  ),
  constraint asphalt_progress_completed_at check (completed_at is null or status = 'COMPLETED'),
  constraint asphalt_progress_revision_positive check (revision >= 1),
  constraint asphalt_progress_device_fk foreign key (user_id, device_id)
    references public.devices(user_id, device_id)
);

create table public.app_settings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  setting_key text not null,
  setting_value jsonb not null,
  client_updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  device_id text,
  last_mutation_id uuid not null,
  revision bigint not null default 1,
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  constraint app_settings_user_key_unique unique (user_id, setting_key),
  constraint app_settings_mutation_unique unique (user_id, last_mutation_id),
  constraint app_settings_key_not_blank check (length(btrim(setting_key)) between 1 and 120),
  constraint app_settings_revision_positive check (revision >= 1),
  constraint app_settings_device_fk foreign key (user_id, device_id)
    references public.devices(user_id, device_id)
);

create table public.day_plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan_date date not null,
  road_keys text[] not null default '{}',
  client_updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  device_id text,
  last_mutation_id uuid not null,
  revision bigint not null default 1,
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  constraint day_plans_user_date_unique unique (user_id, plan_date),
  constraint day_plans_mutation_unique unique (user_id, last_mutation_id),
  constraint day_plans_revision_positive check (revision >= 1),
  constraint day_plans_device_fk foreign key (user_id, device_id)
    references public.devices(user_id, device_id)
);

create or replace function public.initialize_revisioned_row()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.revision := 1;
  new.created_at := statement_timestamp();
  new.server_updated_at := statement_timestamp();
  return new;
end;
$$;

create trigger road_progress_initialize before insert on public.road_progress
for each row execute function public.initialize_revisioned_row();
create trigger measurement_tracks_initialize before insert on public.measurement_tracks
for each row execute function public.initialize_revisioned_row();
create trigger asphalt_plans_initialize before insert on public.asphalt_plans
for each row execute function public.initialize_revisioned_row();
create trigger asphalt_progress_initialize before insert on public.asphalt_progress
for each row execute function public.initialize_revisioned_row();
create trigger app_settings_initialize before insert on public.app_settings
for each row execute function public.initialize_revisioned_row();
create trigger day_plans_initialize before insert on public.day_plans
for each row execute function public.initialize_revisioned_row();

-- The client must send its base revision in NEW.revision. This trigger rejects
-- stale writes, then owns the server timestamp and next revision.
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
    raise exception using errcode = '40001', message = 'revision conflict';
  end if;
  new.created_at := old.created_at;
  new.revision := old.revision + 1;
  new.server_updated_at := statement_timestamp();
  return new;
end;
$$;

create trigger road_progress_revision before update on public.road_progress
for each row execute function public.apply_revisioned_update('user_id', 'road_key');
create trigger measurement_tracks_revision before update on public.measurement_tracks
for each row execute function public.apply_revisioned_update('user_id', '');
create trigger asphalt_plans_revision before update on public.asphalt_plans
for each row execute function public.apply_revisioned_update('owner_user_id', 'plan_key');
create trigger asphalt_progress_revision before update on public.asphalt_progress
for each row execute function public.apply_revisioned_update('user_id', 'plan_id');
create trigger app_settings_revision before update on public.app_settings
for each row execute function public.apply_revisioned_update('user_id', 'setting_key');
create trigger day_plans_revision before update on public.day_plans
for each row execute function public.apply_revisioned_update('user_id', 'plan_date');

create or replace function public.set_profile_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.id := old.id;
  new.created_at := old.created_at;
  new.updated_at := statement_timestamp();
  return new;
end;
$$;

create trigger profiles_updated_at before update on public.profiles
for each row execute function public.set_profile_updated_at();

create or replace function public.create_profile_for_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name, initials)
  values (new.id, new.raw_user_meta_data ->> 'display_name', new.raw_user_meta_data ->> 'initials')
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger auth_user_created
after insert on auth.users
for each row execute function public.create_profile_for_new_user();

create index road_progress_pull_idx on public.road_progress (user_id, server_updated_at, id);
create index road_progress_status_idx on public.road_progress (user_id, status) where deleted_at is null;
create index road_progress_deleted_idx on public.road_progress (user_id, deleted_at) where deleted_at is not null;
create index devices_last_seen_idx on public.devices (user_id, last_seen_at desc);
create index measurement_tracks_pull_idx on public.measurement_tracks (user_id, server_updated_at, id);
create index measurement_tracks_road_idx on public.measurement_tracks (user_id, road_key, started_at);
create index asphalt_plans_pull_idx on public.asphalt_plans (owner_user_id, server_updated_at, id);
create index asphalt_progress_pull_idx on public.asphalt_progress (user_id, server_updated_at, id);
create index asphalt_progress_status_idx on public.asphalt_progress (user_id, status) where deleted_at is null;
create index app_settings_pull_idx on public.app_settings (user_id, server_updated_at, id);
create index day_plans_pull_idx on public.day_plans (user_id, server_updated_at, id);

alter table public.profiles enable row level security;
alter table public.devices enable row level security;
alter table public.road_progress enable row level security;
alter table public.measurement_tracks enable row level security;
alter table public.asphalt_plans enable row level security;
alter table public.asphalt_progress enable row level security;
alter table public.app_settings enable row level security;
alter table public.day_plans enable row level security;

create policy profiles_select_own on public.profiles for select to authenticated using ((select auth.uid()) = id);
create policy profiles_insert_own on public.profiles for insert to authenticated with check ((select auth.uid()) = id);
create policy profiles_update_own on public.profiles for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);
create policy profiles_delete_own on public.profiles for delete to authenticated using ((select auth.uid()) = id);

create policy devices_select_own on public.devices for select to authenticated using ((select auth.uid()) = user_id);
create policy devices_insert_own on public.devices for insert to authenticated with check ((select auth.uid()) = user_id);
create policy devices_update_own on public.devices for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy devices_delete_own on public.devices for delete to authenticated using ((select auth.uid()) = user_id);

create policy road_progress_select_own on public.road_progress for select to authenticated using ((select auth.uid()) = user_id);
create policy road_progress_insert_own on public.road_progress for insert to authenticated with check ((select auth.uid()) = user_id);
create policy road_progress_update_own on public.road_progress for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy road_progress_delete_own on public.road_progress for delete to authenticated using ((select auth.uid()) = user_id);

create policy measurement_tracks_select_own on public.measurement_tracks for select to authenticated using ((select auth.uid()) = user_id);
create policy measurement_tracks_insert_own on public.measurement_tracks for insert to authenticated with check ((select auth.uid()) = user_id);
create policy measurement_tracks_update_own on public.measurement_tracks for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy measurement_tracks_delete_own on public.measurement_tracks for delete to authenticated using ((select auth.uid()) = user_id);

create policy asphalt_plans_select_own on public.asphalt_plans for select to authenticated using ((select auth.uid()) = owner_user_id);
create policy asphalt_plans_insert_own on public.asphalt_plans for insert to authenticated with check ((select auth.uid()) = owner_user_id);
create policy asphalt_plans_update_own on public.asphalt_plans for update to authenticated using ((select auth.uid()) = owner_user_id) with check ((select auth.uid()) = owner_user_id);
create policy asphalt_plans_delete_own on public.asphalt_plans for delete to authenticated using ((select auth.uid()) = owner_user_id);

create policy asphalt_progress_select_own on public.asphalt_progress for select to authenticated using ((select auth.uid()) = user_id);
create policy asphalt_progress_insert_own on public.asphalt_progress for insert to authenticated with check (
  (select auth.uid()) = user_id and exists (
    select 1 from public.asphalt_plans p where p.id = plan_id and p.owner_user_id = (select auth.uid())
  )
);
create policy asphalt_progress_update_own on public.asphalt_progress for update to authenticated using ((select auth.uid()) = user_id) with check (
  (select auth.uid()) = user_id and exists (
    select 1 from public.asphalt_plans p where p.id = plan_id and p.owner_user_id = (select auth.uid())
  )
);
create policy asphalt_progress_delete_own on public.asphalt_progress for delete to authenticated using ((select auth.uid()) = user_id);

create policy app_settings_select_own on public.app_settings for select to authenticated using ((select auth.uid()) = user_id);
create policy app_settings_insert_own on public.app_settings for insert to authenticated with check ((select auth.uid()) = user_id);
create policy app_settings_update_own on public.app_settings for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy app_settings_delete_own on public.app_settings for delete to authenticated using ((select auth.uid()) = user_id);

create policy day_plans_select_own on public.day_plans for select to authenticated using ((select auth.uid()) = user_id);
create policy day_plans_insert_own on public.day_plans for insert to authenticated with check ((select auth.uid()) = user_id);
create policy day_plans_update_own on public.day_plans for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy day_plans_delete_own on public.day_plans for delete to authenticated using ((select auth.uid()) = user_id);

revoke all on function public.apply_revisioned_update() from public, anon, authenticated;
revoke all on function public.initialize_revisioned_row() from public, anon, authenticated;
revoke all on function public.set_profile_updated_at() from public, anon, authenticated;
revoke all on function public.create_profile_for_new_user() from public, anon, authenticated;

grant usage on schema public to authenticated;
grant select, insert, update, delete on public.profiles to authenticated;
grant select, insert, update, delete on public.devices to authenticated;
grant select, insert, update, delete on public.road_progress to authenticated;
grant select, insert, update, delete on public.measurement_tracks to authenticated;
grant select, insert, update, delete on public.asphalt_plans to authenticated;
grant select, insert, update, delete on public.asphalt_progress to authenticated;
grant select, insert, update, delete on public.app_settings to authenticated;
grant select, insert, update, delete on public.day_plans to authenticated;

revoke all on public.profiles from anon;
revoke all on public.devices from anon;
revoke all on public.road_progress from anon;
revoke all on public.measurement_tracks from anon;
revoke all on public.asphalt_plans from anon;
revoke all on public.asphalt_progress from anon;
revoke all on public.app_settings from anon;
revoke all on public.day_plans from anon;
