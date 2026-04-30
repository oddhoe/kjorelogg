# Android Studio / Capacitor

Denne mappen er klargjort for en enkel Capacitor-wrapper rundt `mr1-fixed.html`.

## Første oppsett

1. Kjør `npm install`
2. Kjør `npm run sync:web`
3. Kjør `npx cap add android`
4. Kjør `npm run android:sync`
5. Kjør `npm run android:open`

Deretter åpnes `android/` i Android Studio.

Merk:
I denne mappen brukes en lokal launcher for Android Studio i stedet for `npx cap open android`, fordi `cap open` kan henge i PowerShell på noen Windows-oppsett selv om prosjektet er korrekt.

## Når du endrer HTML-fila

1. Lagre endringer i `mr1-fixed.html`
2. Kjør `npm run sync:web`
3. Kjør `npm run android:sync`

## PDF på Android

`mr1-fixed.html` er nå satt opp til å:

- bruke lokale JS/CSS-filer i `vendor/`
- prøve native lagring via Capacitor Filesystem i app-modus
- dele/åpne lagret PDF via Capacitor Share når tilgjengelig

Målet på Android er at PDF skal lagres under:

`Dokumenter/Kjorelogg/`

Hvis du bygger en ny APK etter dette oppsettet, er PDF-flyten mye mer robust enn ren `doc.save(...)` i WebView.
