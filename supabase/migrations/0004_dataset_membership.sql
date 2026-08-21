-- FASE 5.9: explicit shared datasets and membership.
-- No existing row is assigned to a dataset by this migration. dataset_id stays
-- NULL until a separately approved, previewed bootstrap migration is run.

create table public.datasets (
  id uuid primary key default gen_random_uuid(),
  dataset_key text not null unique,
  name text not null,
  county text,
  vehicle text,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default statement_timestamp(),
  server_updated_at timestamptz not null default statement_timestamp(),
  archived_at timestamptz,
  constraint datasets_key_not_blank check (length(btrim(dataset_key)) between 1 and 200),
  constraint datasets_name_not_blank check (length(btrim(name)) between 1 and 200)
);

create table public.dataset_members (
  dataset_id uuid not null references public.datasets(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null,
  active boolean not null default true,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default statement_timestamp(),
  updated_at timestamptz not null default statement_timestamp(),
  primary key (dataset_id, user_id),
  constraint dataset_members_role check (role in ('owner', 'admin', 'driver', 'read_only'))
);

create index dataset_members_user_idx
  on public.dataset_members (user_id, active, dataset_id);

alter table public.datasets enable row level security;
alter table public.dataset_members enable row level security;

-- SECURITY DEFINER avoids recursive dataset_members RLS evaluation. The result
-- is always bound to auth.uid(); callers cannot ask on behalf of another user.
create or replace function public.is_dataset_member(
  p_dataset_id uuid,
  p_require_write boolean default false
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.dataset_members m
    where m.dataset_id = p_dataset_id
      and m.user_id = auth.uid()
      and m.active
      and (not p_require_write or m.role in ('owner', 'admin', 'driver'))
  );
$$;

create or replace function public.is_dataset_admin(p_dataset_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.dataset_members m
    where m.dataset_id = p_dataset_id
      and m.user_id = auth.uid()
      and m.active
      and m.role in ('owner', 'admin')
  );
$$;

create policy datasets_select_member on public.datasets
  for select to authenticated
  using (public.is_dataset_member(id, false));
create policy datasets_update_admin on public.datasets
  for update to authenticated
  using (public.is_dataset_admin(id))
  with check (public.is_dataset_admin(id));

create policy dataset_members_select_member on public.dataset_members
  for select to authenticated
  using (public.is_dataset_member(dataset_id, false));
create policy dataset_members_insert_admin on public.dataset_members
  for insert to authenticated
  with check (public.is_dataset_admin(dataset_id) and created_by = (select auth.uid()));
create policy dataset_members_update_admin on public.dataset_members
  for update to authenticated
  using (public.is_dataset_admin(dataset_id))
  with check (public.is_dataset_admin(dataset_id));

-- Dataset creation and its first owner membership are one atomic operation.
create or replace function public.create_dataset(
  p_dataset_key text,
  p_name text,
  p_county text default null,
  p_vehicle text default null
)
returns public.datasets
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_dataset public.datasets;
begin
  if v_user is null then
    raise sqlstate 'PT401' using message = 'authentication required';
  end if;
  insert into public.datasets (dataset_key, name, county, vehicle, created_by)
  values (btrim(p_dataset_key), btrim(p_name), p_county, p_vehicle, v_user)
  returning * into v_dataset;
  insert into public.dataset_members
    (dataset_id, user_id, role, active, created_by)
  values (v_dataset.id, v_user, 'owner', true, v_user);
  return v_dataset;
end;
$$;

create or replace function public.add_dataset_member(
  p_dataset_id uuid,
  p_user_id uuid,
  p_role text
)
returns public.dataset_members
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_result public.dataset_members;
begin
  if not public.is_dataset_admin(p_dataset_id) then
    raise sqlstate 'PT403' using message = 'dataset admin role required';
  end if;
  if p_role not in ('owner', 'admin', 'driver', 'read_only') then
    raise sqlstate 'PT400' using message = 'invalid dataset role';
  end if;
  insert into public.dataset_members
    (dataset_id, user_id, role, active, created_by)
  values (p_dataset_id, p_user_id, p_role, true, auth.uid())
  on conflict (dataset_id, user_id) do update set
    role = excluded.role,
    active = true,
    updated_at = statement_timestamp()
  returning * into v_result;
  return v_result;
end;
$$;

-- Nullable compatibility columns. Existing rows remain legacy user-owned rows.
alter table public.road_progress
  add column dataset_id uuid references public.datasets(id) on delete restrict,
  add column created_by uuid references auth.users(id) on delete restrict,
  add column updated_by uuid references auth.users(id) on delete restrict,
  add column updated_device_id text;
alter table public.measurement_tracks
  add column dataset_id uuid references public.datasets(id) on delete restrict,
  add column created_by uuid references auth.users(id) on delete restrict,
  add column updated_by uuid references auth.users(id) on delete restrict,
  add column updated_device_id text;
alter table public.asphalt_plans
  add column dataset_id uuid references public.datasets(id) on delete restrict,
  add column created_by uuid references auth.users(id) on delete restrict,
  add column updated_by uuid references auth.users(id) on delete restrict,
  add column updated_device_id text;
alter table public.asphalt_progress
  add column dataset_id uuid references public.datasets(id) on delete restrict,
  add column created_by uuid references auth.users(id) on delete restrict,
  add column updated_by uuid references auth.users(id) on delete restrict,
  add column updated_device_id text;
alter table public.app_settings
  add column dataset_id uuid references public.datasets(id) on delete restrict,
  add column created_by uuid references auth.users(id) on delete restrict,
  add column updated_by uuid references auth.users(id) on delete restrict,
  add column updated_device_id text;
alter table public.day_plans
  add column dataset_id uuid references public.datasets(id) on delete restrict,
  add column created_by uuid references auth.users(id) on delete restrict,
  add column updated_by uuid references auth.users(id) on delete restrict,
  add column updated_device_id text;

-- A plan/progress pair may not cross dataset boundaries. MATCH SIMPLE preserves
-- legacy NULL-dataset rows without assigning them implicitly.
alter table public.asphalt_plans
  add constraint asphalt_plans_id_dataset_unique unique (id, dataset_id);
alter table public.asphalt_progress
  add constraint asphalt_progress_plan_dataset_fk
  foreign key (plan_id, dataset_id)
  references public.asphalt_plans(id, dataset_id) on delete cascade;

alter table public.road_progress drop constraint road_progress_user_road_unique;
alter table public.measurement_tracks drop constraint measurement_tracks_user_session_direction_unique;
alter table public.asphalt_plans drop constraint asphalt_plans_owner_key_unique;
alter table public.asphalt_progress drop constraint asphalt_progress_user_plan_unique;
alter table public.app_settings drop constraint app_settings_user_key_unique;
alter table public.day_plans drop constraint day_plans_user_date_unique;

create unique index road_progress_legacy_user_key_unique
  on public.road_progress (user_id, road_key) where dataset_id is null;
create unique index measurement_tracks_legacy_session_unique
  on public.measurement_tracks (user_id, session_id, road_key, direction) where dataset_id is null;
create unique index asphalt_plans_legacy_owner_key_unique
  on public.asphalt_plans (owner_user_id, plan_key) where dataset_id is null;
create unique index asphalt_progress_legacy_user_plan_unique
  on public.asphalt_progress (user_id, plan_id) where dataset_id is null;
create unique index app_settings_legacy_user_key_unique
  on public.app_settings (user_id, setting_key) where dataset_id is null;
create unique index day_plans_legacy_user_date_unique
  on public.day_plans (user_id, plan_date) where dataset_id is null;

create unique index road_progress_dataset_key_unique
  on public.road_progress (dataset_id, road_key) where dataset_id is not null;
create unique index measurement_tracks_dataset_session_unique
  on public.measurement_tracks (dataset_id, session_id, road_key, direction)
  where dataset_id is not null;
create unique index asphalt_plans_dataset_key_unique
  on public.asphalt_plans (dataset_id, plan_key) where dataset_id is not null;
create unique index asphalt_progress_dataset_plan_unique
  on public.asphalt_progress (dataset_id, plan_id) where dataset_id is not null;
create unique index app_settings_dataset_key_unique
  on public.app_settings (dataset_id, setting_key) where dataset_id is not null;
create unique index day_plans_dataset_date_unique
  on public.day_plans (dataset_id, plan_date) where dataset_id is not null;

create index road_progress_dataset_pull_idx
  on public.road_progress (dataset_id, server_updated_at, id) where dataset_id is not null;
create index asphalt_plans_dataset_pull_idx
  on public.asphalt_plans (dataset_id, server_updated_at, id) where dataset_id is not null;
create index asphalt_progress_dataset_pull_idx
  on public.asphalt_progress (dataset_id, server_updated_at, id) where dataset_id is not null;

-- Replace user-only policies with dual-mode policies:
--   dataset_id IS NULL: unchanged legacy owner isolation
--   dataset_id IS NOT NULL: active dataset membership
drop policy road_progress_select_own on public.road_progress;
drop policy road_progress_insert_own on public.road_progress;
drop policy road_progress_update_own on public.road_progress;
drop policy road_progress_delete_own on public.road_progress;
create policy road_progress_select_scope on public.road_progress for select to authenticated
  using ((dataset_id is null and (select auth.uid()) = user_id) or public.is_dataset_member(dataset_id, false));
create policy road_progress_insert_scope on public.road_progress for insert to authenticated
  with check ((dataset_id is null and (select auth.uid()) = user_id) or (public.is_dataset_member(dataset_id, true) and created_by = (select auth.uid()) and updated_by = (select auth.uid())));
create policy road_progress_update_scope on public.road_progress for update to authenticated
  using ((dataset_id is null and (select auth.uid()) = user_id) or public.is_dataset_member(dataset_id, true))
  with check ((dataset_id is null and (select auth.uid()) = user_id) or (public.is_dataset_member(dataset_id, true) and updated_by = (select auth.uid())));

drop policy measurement_tracks_select_own on public.measurement_tracks;
drop policy measurement_tracks_insert_own on public.measurement_tracks;
drop policy measurement_tracks_update_own on public.measurement_tracks;
drop policy measurement_tracks_delete_own on public.measurement_tracks;
create policy measurement_tracks_select_scope on public.measurement_tracks for select to authenticated
  using ((dataset_id is null and (select auth.uid()) = user_id) or public.is_dataset_member(dataset_id, false));
create policy measurement_tracks_insert_scope on public.measurement_tracks for insert to authenticated
  with check ((dataset_id is null and (select auth.uid()) = user_id) or (public.is_dataset_member(dataset_id, true) and created_by = (select auth.uid()) and updated_by = (select auth.uid())));
create policy measurement_tracks_update_scope on public.measurement_tracks for update to authenticated
  using ((dataset_id is null and (select auth.uid()) = user_id) or public.is_dataset_member(dataset_id, true))
  with check ((dataset_id is null and (select auth.uid()) = user_id) or (public.is_dataset_member(dataset_id, true) and updated_by = (select auth.uid())));

drop policy asphalt_plans_select_own on public.asphalt_plans;
drop policy asphalt_plans_insert_own on public.asphalt_plans;
drop policy asphalt_plans_update_own on public.asphalt_plans;
drop policy asphalt_plans_delete_own on public.asphalt_plans;
create policy asphalt_plans_select_scope on public.asphalt_plans for select to authenticated
  using ((dataset_id is null and (select auth.uid()) = owner_user_id) or public.is_dataset_member(dataset_id, false));
create policy asphalt_plans_insert_scope on public.asphalt_plans for insert to authenticated
  with check ((dataset_id is null and (select auth.uid()) = owner_user_id) or (public.is_dataset_member(dataset_id, true) and created_by = (select auth.uid()) and updated_by = (select auth.uid())));
create policy asphalt_plans_update_scope on public.asphalt_plans for update to authenticated
  using ((dataset_id is null and (select auth.uid()) = owner_user_id) or public.is_dataset_member(dataset_id, true))
  with check ((dataset_id is null and (select auth.uid()) = owner_user_id) or (public.is_dataset_member(dataset_id, true) and updated_by = (select auth.uid())));

drop policy asphalt_progress_select_own on public.asphalt_progress;
drop policy asphalt_progress_insert_own on public.asphalt_progress;
drop policy asphalt_progress_update_own on public.asphalt_progress;
drop policy asphalt_progress_delete_own on public.asphalt_progress;
create policy asphalt_progress_select_scope on public.asphalt_progress for select to authenticated
  using ((dataset_id is null and (select auth.uid()) = user_id) or public.is_dataset_member(dataset_id, false));
create policy asphalt_progress_insert_scope on public.asphalt_progress for insert to authenticated
  with check ((dataset_id is null and (select auth.uid()) = user_id and exists (select 1 from public.asphalt_plans p where p.id = plan_id and p.owner_user_id = (select auth.uid()))) or (public.is_dataset_member(dataset_id, true) and created_by = (select auth.uid()) and updated_by = (select auth.uid())));
create policy asphalt_progress_update_scope on public.asphalt_progress for update to authenticated
  using ((dataset_id is null and (select auth.uid()) = user_id) or public.is_dataset_member(dataset_id, true))
  with check ((dataset_id is null and (select auth.uid()) = user_id) or (public.is_dataset_member(dataset_id, true) and updated_by = (select auth.uid())));

drop policy app_settings_select_own on public.app_settings;
drop policy app_settings_insert_own on public.app_settings;
drop policy app_settings_update_own on public.app_settings;
drop policy app_settings_delete_own on public.app_settings;
create policy app_settings_select_scope on public.app_settings for select to authenticated
  using ((dataset_id is null and (select auth.uid()) = user_id) or public.is_dataset_member(dataset_id, false));
create policy app_settings_insert_scope on public.app_settings for insert to authenticated
  with check ((dataset_id is null and (select auth.uid()) = user_id) or (public.is_dataset_member(dataset_id, true) and created_by = (select auth.uid()) and updated_by = (select auth.uid())));
create policy app_settings_update_scope on public.app_settings for update to authenticated
  using ((dataset_id is null and (select auth.uid()) = user_id) or public.is_dataset_member(dataset_id, true))
  with check ((dataset_id is null and (select auth.uid()) = user_id) or (public.is_dataset_member(dataset_id, true) and updated_by = (select auth.uid())));

drop policy day_plans_select_own on public.day_plans;
drop policy day_plans_insert_own on public.day_plans;
drop policy day_plans_update_own on public.day_plans;
drop policy day_plans_delete_own on public.day_plans;
create policy day_plans_select_scope on public.day_plans for select to authenticated
  using ((dataset_id is null and (select auth.uid()) = user_id) or public.is_dataset_member(dataset_id, false));
create policy day_plans_insert_scope on public.day_plans for insert to authenticated
  with check ((dataset_id is null and (select auth.uid()) = user_id) or (public.is_dataset_member(dataset_id, true) and created_by = (select auth.uid()) and updated_by = (select auth.uid())));
create policy day_plans_update_scope on public.day_plans for update to authenticated
  using ((dataset_id is null and (select auth.uid()) = user_id) or public.is_dataset_member(dataset_id, true))
  with check ((dataset_id is null and (select auth.uid()) = user_id) or (public.is_dataset_member(dataset_id, true) and updated_by = (select auth.uid())));

grant select on public.datasets to authenticated;
grant select on public.dataset_members to authenticated;
revoke insert, update, delete on public.datasets from authenticated;
revoke insert, update, delete on public.dataset_members from authenticated;
revoke all on public.datasets from anon;
revoke all on public.dataset_members from anon;

revoke all on function public.is_dataset_member(uuid, boolean) from public, anon, authenticated;
revoke all on function public.is_dataset_admin(uuid) from public, anon, authenticated;
revoke all on function public.create_dataset(text, text, text, text) from public, anon;
revoke all on function public.add_dataset_member(uuid, uuid, text) from public, anon;
grant execute on function public.create_dataset(text, text, text, text) to authenticated;
grant execute on function public.add_dataset_member(uuid, uuid, text) to authenticated;
grant execute on function public.is_dataset_member(uuid, boolean) to authenticated;
grant execute on function public.is_dataset_admin(uuid) to authenticated;
