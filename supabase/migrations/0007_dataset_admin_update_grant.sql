-- FASE 6.1 runtime correction.
-- datasets_update_admin already restricts UPDATE to active owner/admin members,
-- but authenticated lacked the table-level UPDATE grant, so PostgreSQL returned
-- 42501 before RLS could evaluate the policy.

grant update on public.datasets to authenticated;
