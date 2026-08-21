-- Provenance from imported asphalt/dekke plans.
-- Operational state remains in asphalt_progress.status.

alter table public.asphalt_plans
  add column source_completed boolean not null default false,
  add column source_completed_reason text,
  add column source_imported_at timestamptz;

alter table public.asphalt_plans
  add constraint asphalt_plans_source_completed_reason check (
    (source_completed and source_completed_reason = 'excel_green' and source_imported_at is not null)
    or (not source_completed and source_completed_reason is null)
  );

comment on column public.asphalt_plans.source_completed is
  'Positive completion provenance from the imported source; not the operational user status.';
comment on column public.asphalt_plans.source_completed_reason is
  'Controlled provenance value. Initial supported value: excel_green.';
