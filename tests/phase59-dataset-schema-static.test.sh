#!/usr/bin/env bash
set -euo pipefail

membership="supabase/migrations/0004_dataset_membership.sql"
fencing="supabase/migrations/0005_work_leases_fencing.sql"

require() { rg -q --multiline "$2" "$1" || { echo "FAIL: $3"; exit 1; }; }

require "$membership" 'create table public\.datasets \(' 'datasets table missing'
require "$membership" 'dataset_key text not null unique' 'dataset_key uniqueness missing'
require "$membership" 'create table public\.dataset_members \(' 'dataset_members missing'
require "$membership" "role in \('owner', 'admin', 'driver', 'read_only'\)" 'roles missing'
require "$membership" 'create or replace function public\.create_dataset' 'create_dataset RPC missing'
require "$membership" 'create or replace function public\.add_dataset_member' 'add member RPC missing'

for table in road_progress measurement_tracks asphalt_plans asphalt_progress app_settings day_plans; do
  require "$membership" "alter table public\\.${table}[[:space:][:print:]]*add column dataset_id" "$table.dataset_id missing"
  require "$membership" "create policy ${table}_(select|insert|update)_scope" "$table dataset policy missing"
done

require "$fencing" 'create table public\.work_leases \([[:space:][:print:]]*dataset_id uuid not null' 'lease not dataset scoped'
require "$fencing" 'work_leases_one_active_dataset_idx[[:space:][:print:]]*\(dataset_id\) where released_at is null' 'single active lease missing'
require "$fencing" 'pg_advisory_xact_lock\(hashtextextended\(p_dataset_id::text' 'atomic acquire lock missing'
require "$fencing" 'coalesce\(max\(fencing_generation\), 0\) \+ 1' 'generation increment missing'
require "$fencing" 'l\.dataset_id = new\.dataset_id[[:space:][:print:]]*l\.fencing_generation = new\.fencing_generation' 'fencing validation missing'
require "$fencing" "raise sqlstate 'PT412' using message = 'stale fencing generation'" 'stale fence response missing'
require "$fencing" "minimum_write_client_version[[:space:][:print:]]*raise sqlstate 'PT426'" 'minimum client gate missing'
require "$fencing" 'create table public\.sync_audit_log \([[:space:][:print:]]*dataset_id uuid not null[[:space:][:print:]]*user_id uuid not null[[:space:][:print:]]*device_id text[[:space:][:print:]]*session_id uuid not null' 'audit attribution missing'

if rg -q "'user:'[[:space:]]*\|\|" "$membership" "$fencing"; then
  echo 'FAIL: auth uid used as dataset identity'
  exit 1
fi
if rg -q 'grant (insert|update|delete) on public\.(work_leases|sync_audit_log)' "$fencing"; then
  echo 'FAIL: client DML grant on protected server table'
  exit 1
fi

echo 'PASS phase59 dataset/membership/lease/fencing static structure'
