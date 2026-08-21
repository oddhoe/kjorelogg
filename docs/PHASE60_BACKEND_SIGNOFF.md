# FASE 6.0 – backend sign-off

Dato: 2026-08-21
Status: **GODKJENT FOR PILOTKLIENT-INTEGRASJON**

Rapporten skiller mellom faktisk observerte Supabase-resultater og kontroller
som ennå ikke er kjørt. Statisk SQL-inspeksjon alene gir ikke `PASS`.

## Schema

| Kontroll | Status | Faktisk metode og resultat | Restrisiko |
|---|---|---|---|
| `datasets`, `dataset_members`, `work_leases`, `sync_runtime_config`, `sync_audit_log` | PASS | Autentisert Data API `SELECT ... head/count` mot hver tabell lyktes. | Bekrefter API-eksponering, ikke hele katalogdefinisjonen. |
| Fagtabeller tilgjengelige etter 0004/0005 | PASS | Autentisert Data API-kall lyktes for `road_progress`, `measurement_tracks`, `asphalt_plans`, `asphalt_progress`, `app_settings` og `day_plans`. | Kolonne-/FK-/indeksmetadata er ikke direkte kataloglest med publishable key. |
| `dataset_id`, `work_session_id`, `fencing_generation`, `deleted_by` | PASS | Reell insert/update og readback på `road_progress` brukte feltene; soft delete returnerte `deleted_by`. | Øvrige fagtabeller er ennå ikke runtime-skrevet. |
| Dataset-FK-er, alle indekser og alle triggere | IKKE TESTET | Finnes i kjørte migreringer, men `pg_catalog` er ikke tilgjengelig med klienttilgangen. Funksjonell triggeradferd er runtime-testet for road. | Full katalogattestasjon krever SQL Editor/adminspørring. |
| RLS aktivert | PASS | Non-member og anon ble avvist, `read_only` write ga 0 rader, og direkte audit INSERT/UPDATE/DELETE fikk `42501`. | Funksjonelt bevist for testbanene. |

## Membership og shared dataset

- TEST_A og TEST_B er separate Supabase Auth-brukere.
- Begge ble medlemmer av `TEST_PHASE60_SHARED`.
- TEST_A shared access: **PASS** via opprettelse, membership og fenced write.
- TEST_B shared SELECT: **PASS**, én forventet dataset-/fagrad ble lest.
- TEST_B før membership: **PASS**, dataset og fagdata ga 0 synlige rader.
- `read_only` SELECT: **PASS**.
- `read_only` write: **PASS (DENIED)**, update ga 0 rader.
- Non-member INSERT: **PASS (DENIED)** med `PT403`.
- Non-member UPDATE: **PASS (DENIED)** med 0 rader.
- Anon SELECT/INSERT/UPDATE: **PASS (DENIED)** med `42501`.

## Lease og heartbeat

| Kontroll | Status | Observert resultat |
|---|---|---|
| TEST_A acquire | PASS | Lease generation 1. |
| TEST_B acquire mens A holdt lease | PASS | Serverfeil `PT423`. |
| TEST_A release | PASS | RPC returnerte released lease. |
| TEST_B acquire etter release | PASS | Lease generation 2. |
| Korrekt heartbeat/renew | PASS | Serverens heartbeat-timestamp ble oppdatert. |
| Feil session | PASS | Serverfeil `PT412`. |
| Feil device | PASS | Serverfeil `PT412` etter 0006. |
| Feil generation | PASS | Serverfeil `PT412` etter 0006. |

Kun én aktiv lease per dataset ble dermed funksjonelt bevist i testforløpet.

## Fencing og revision

- Generation 1 ble gammel etter kontrollert release og generation 2-acquire.
- Write med gammel generation 1: **PASS (DENIED)** med serverkode `PT412`.
- Korrekt revision + korrekt fencing: **PASS**, revision 1 → 2.
- Stale revision + korrekt fencing: **PASS (DENIED)** med `PT409`.
- Revision og fencing er dermed uavhengige serverbarrierer for den testede road-raden.
- `dataset_id` nullstilling: **PASS (DENIED)** med `22023`.
- `dataset_id` flytting: **PASS (DENIED)** med `22023`.
- Legacy NULL-path kunne ikke omgå dataset-fencing: **PASS**.

## Idempotens og audit

Samme mutation UUID ble sendt ti ganger etter første vellykkede oppdatering.

- Ekstra faglig servereffekt: **0**.
- Ekstra revisionøkning: **0**.
- Audit-events for mutation UUID: **nøyaktig 1**.
- Audit-readback inneholdt dataset, Auth-bruker, device, session, mutation UUID,
  revision, status, fencing generation, client version og servertimestamp: **PASS**.
- Direkte audit INSERT: **DENIED**, SQLSTATE `42501`.
- Direkte audit UPDATE/DELETE: **DENIED**, SQLSTATE `42501`.

## Soft delete

- `deleted_at`: **PASS**.
- `deleted_by`: **PASS**.
- Revision increment: **PASS**.
- Fysisk rad beholdt: **PASS**.
- Normal fysisk DELETE: **DENIED**, 0 returnerte/slettede rader.

## Minimum klientversjon

- `sync_runtime_config.minimum_write_client_version = v2.0.105`: **PASS**.
- v2.0.104 fenced write: **DENIED** med `PT426`.
- v2.0.105 fenced write: **PASS** når membership, lease og revision var gyldige.

## Cleanup og produksjon

- Full `TEST_PHASE60_*` cleanup: **PASS** via 0006-RPC. Faktisk slettet:
  1 dataset, 2 memberships, 2 leases, 1 road row og 3 audit rows; øvrige
  testtabeller hadde 0 rader. Etterkontroll viste 0 `TEST_PHASE60` datasets.
- Cleanup av ikke-test-prefiks: **PASS (DENIED)** med `PT403`. Kontroll-datasettet
  ble deretter eksplisitt omdøpt til testprefiks og ryddet.
- Eksisterende lokal fremdrift/asfalt/GPS/comments ble ikke lastet opp: **PASS**.
- Lokal IndexedDB ble ikke åpnet av backendtestflaten: **PASS**.
- Produksjonsentrypoints har SHA-256
  `11d36e1a0b7d7fbdf6c4ad94d54b9d1f1ac8c532b77b23e753d34452538ab4f7`: **PASS**.

## Sign-off-matrise

```text
Schema runtime                      PASS (funksjonelt; full katalogmetadata IKKE TESTET)
Shared dataset A/B                  PASS
Non-member isolation               PASS
read_only enforcement              PASS
Anon denied                        PASS
Atomic acquire                     PASS
Second-driver PT423                PASS
Heartbeat                          PASS
Renew negative cases               PASS
Fencing generation                 PASS
Old fencing PT412                  PASS
Revision protection PT409          PASS
Revision + fencing independent     PASS
Idempotency 10x                    PASS
Audit exactly once                 PASS
Audit write protection             PASS
Soft delete                        PASS
Physical delete denied             PASS
Minimum client version             PASS
dataset_id move/null bypass        PASS
Test cleanup                       PASS
Production untouched               PASS
Local v4 baseline untouched        PASS
```

## Gate

`BACKEND SIGN-OFF: APPROVED FOR PILOT CLIENT INTEGRATION`

0006 og 0007 ble kjørt manuelt med `Success. No rows returned`. Etter 0007
fullførte den isolerte runtime-regresjonen uten feil. Katalogmetadata som krever
admin/SQL Editor er fortsatt eksplisitt merket `IKKE TESTET`; alle kritiske
funksjonelle gates for pilotklienten er runtime-PASS.
