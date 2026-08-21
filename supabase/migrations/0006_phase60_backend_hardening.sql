-- FASE 6.1: close two runtime sign-off gaps found after 0004/0005.
-- 1. A lease renewal must prove the device id as well as user/session/generation.
-- 2. A dataset owner needs a narrowly scoped cleanup RPC for isolated TEST_PHASE*
--    verification datasets. The RPC cannot target a production dataset.

drop function public.renew_work_lease(uuid, uuid, bigint);

create or replace function public.renew_work_lease(
  p_lease_id uuid,
  p_device_id text,
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
  if auth.uid() is null then
    raise sqlstate 'PT401' using message = 'authentication required';
  end if;
  select lease_ttl_seconds into v_ttl
    from public.sync_runtime_config where singleton;
  update public.work_leases set
    last_heartbeat_at = v_now,
    expires_at = v_now + make_interval(secs => v_ttl),
    server_updated_at = v_now
  where id = p_lease_id
    and user_id = auth.uid()
    and device_id = p_device_id
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

revoke all on function public.renew_work_lease(uuid, text, uuid, bigint)
  from public, anon;
grant execute on function public.renew_work_lease(uuid, text, uuid, bigint)
  to authenticated;

create or replace function public.cleanup_test_dataset(p_dataset_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_key text;
  v_road integer := 0;
  v_tracks integer := 0;
  v_asphalt_progress integer := 0;
  v_asphalt_plans integer := 0;
  v_settings integer := 0;
  v_day_plans integer := 0;
  v_leases integer := 0;
  v_audit integer := 0;
  v_members integer := 0;
  v_datasets integer := 0;
begin
  if auth.uid() is null then
    raise sqlstate 'PT401' using message = 'authentication required';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_dataset_id::text, 0));
  select dataset_key into v_key
    from public.datasets
    where id = p_dataset_id
    for update;
  if not found then
    raise sqlstate 'PT404' using message = 'test dataset not found';
  end if;
  if v_key !~ '^TEST_PHASE[0-9]+_' then
    raise sqlstate 'PT403'
      using message = 'cleanup is restricted to TEST_PHASE datasets';
  end if;
  if not public.is_dataset_admin(p_dataset_id) then
    raise sqlstate 'PT403' using message = 'dataset admin role required';
  end if;

  delete from public.asphalt_progress where dataset_id = p_dataset_id;
  get diagnostics v_asphalt_progress = row_count;
  delete from public.asphalt_plans where dataset_id = p_dataset_id;
  get diagnostics v_asphalt_plans = row_count;
  delete from public.measurement_tracks where dataset_id = p_dataset_id;
  get diagnostics v_tracks = row_count;
  delete from public.road_progress where dataset_id = p_dataset_id;
  get diagnostics v_road = row_count;
  delete from public.app_settings where dataset_id = p_dataset_id;
  get diagnostics v_settings = row_count;
  delete from public.day_plans where dataset_id = p_dataset_id;
  get diagnostics v_day_plans = row_count;
  delete from public.sync_audit_log where dataset_id = p_dataset_id;
  get diagnostics v_audit = row_count;
  delete from public.work_leases where dataset_id = p_dataset_id;
  get diagnostics v_leases = row_count;
  delete from public.dataset_members where dataset_id = p_dataset_id;
  get diagnostics v_members = row_count;
  delete from public.datasets where id = p_dataset_id;
  get diagnostics v_datasets = row_count;

  return jsonb_build_object(
    'dataset_key', v_key,
    'road_progress', v_road,
    'measurement_tracks', v_tracks,
    'asphalt_progress', v_asphalt_progress,
    'asphalt_plans', v_asphalt_plans,
    'app_settings', v_settings,
    'day_plans', v_day_plans,
    'sync_audit_log', v_audit,
    'work_leases', v_leases,
    'dataset_members', v_members,
    'datasets', v_datasets
  );
end;
$$;

revoke all on function public.cleanup_test_dataset(uuid) from public, anon;
grant execute on function public.cleanup_test_dataset(uuid) to authenticated;
