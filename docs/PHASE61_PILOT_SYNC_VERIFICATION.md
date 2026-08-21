# FASE 6.1 – pilot-sync-verifikasjon

Dato: 2026-08-21
Pilotklient: `v2.0.105`
Produksjonsaktivering: **NEI**

## Backend sign-off

Backend er godkjent i `PHASE60_BACKEND_SIGNOFF.md`. 0004–0007 er kjørt mot
ekte Supabase. Alle kritiske funksjonelle gates er runtime-PASS.

## Klientarkitektur

Pilotklienten bruker `pilot-sync-v105.js`. Den gamle `sync-engine.js::syncNow()`
er ikke kallbar fra pilotens write-path. Ny rekkefølge er:

```text
client version check
→ server preflight
→ pull med cursor
→ merge/conflict
→ acquire/renew dataset lease
→ push test-outbox
→ ack og fjern mutation
```

Motoren avviser alle entity keys og dataset keys som ikke starter med
`TEST_PHASE61_`. Eksisterende lokal veg-, geometri-, asfalt-, kommentar- og
route-state blir verken tilordnet, enqueued eller lastet opp.

## Faktisk runtime-test

Testen brukte to separate Auth-brukere, et eget `TEST_PHASE61_*`-datasett og
isolerte IndexedDB-er (`nvdb_tiles_phase61_test` og klient-B-varianten).

Observerte resultater:

- TEST_A og TEST_B login: PASS.
- Shared dataset og membership: PASS.
- Preflight/pull/lease/push-rekkefølge: PASS.
- Second-driver ble mappet fra `PT423` til locked state: PASS.
- Offline mutation ble beholdt: PASS.
- Outbox overlevde ny repository-instans: PASS.
- Reconnect kjørte pull-before-push og ack: PASS.
- Stale klient trakk remote først og bevarte local/remote konfliktpayload: PASS.
- Cleanup slettet 1 dataset, 2 leases, 2 memberships, 3 road rows og 4 audit
  rows. Etterkontroll viste 0 TEST_PHASE61-serverdatasett: PASS.

## Restrisiko og ikke testet

- Eksakte veggklokkeintervaller 30 sek / 5 min / 30 min: IKKE TESTET. Den
  persistente offline/restart-mekanismen er runtime-testet uten å vente disse
  intervallene.
- Full Chrome-restart på primærenhet etter same-origin deploy: IKKE TESTET.
- Hash av de sju primære lokale fagrecordene før/etter same-origin test:
  IKKE TESTET før deploy. Pilotens eksisterende baseline-vakt er beholdt.
- Asfalt-sync med TEST_PHASE61-plan: IKKE TESTET i denne deltesten; backendens
  plan-key→UUID-mekanisme er tidligere runtime-testet i FASE 4.2.

## Verifikasjonsmatrise

```text
Backend sign-off                       PASS
Pilot client version                   v2.0.105
New sync ordering                      PASS
Dataset membership                     PASS
Preflight before push                  PASS
Pull before push                       PASS
Lease acquire                          PASS
Second-driver UI/state                 PASS
Persistent outbox                      PASS
Offline working                        PASS
Reconnect reconciliation               PASS
Fencing protection                     PASS (backend); client stale path PASS
Revision protection                    PASS (backend)
Stale-client protection                PASS
Minimum client version                 PASS
Conflict preservation                  PASS
Local baseline unchanged               IKKE TESTET på primærenhet etter deploy
Existing local data uploaded           NEI
Production unchanged                   PASS
```

Pilot er ikke produksjonsaktivert. Same-origin primærenhetstest må fullføres
før status kan oppgraderes til endelig FASE 6.1 runtime-PASS.
