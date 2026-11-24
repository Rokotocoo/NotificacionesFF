# Alertas ForexFactory → móvil (ntfy)

Recibes en el teléfono tres tipos de aviso:

| Aviso | De dónde sale | Dónde corre |
|---|---|---|
| 📅 Resumen diario + ⏰ aviso previo de eventos 🔴/🟠 del calendario | Feed oficial del calendario de ForexFactory | GitHub (24/7) |
| 📰 Noticias en vivo filtradas por temas (Fed, CPI, NFP, tasas…) | FinancialJuice + InvestingLive | GitHub (24/7) |
| 🔴/🟠 FF News: noticias en vivo de ForexFactory con su color exacto | forexfactory.com/news | Tu Mac (encendido) |

---

## Parte 1 — GitHub (calendario + noticias en vivo 24/7)

1. Crea un repositorio **privado** en github.com.
2. **Add file → Upload files** → sube `bot.py`.
3. **Add file → Create new file** → nombre `.github/workflows/alerts.yml` → pega el contenido de `alerts.yml` → Commit.
4. **Settings → Secrets and variables → Actions**
   - *Secrets*: `NTFY_TOPIC` = el nombre de tu tema
   - *Variables* (opcionales):
     - `TZ_NAME` → tu zona horaria, ej. `Europe/Lisbon`, `Asia/Dubai`
     - `ALERT_MINUTES` → antelación de los avisos del calendario (por defecto 15)
     - `SUMMARY_HOUR` → hora del resumen diario (por defecto 7)
     - `CURRENCIES` → filtrar divisas del calendario, ej. `USD,EUR,GBP`
     - `KEYWORDS` → temas para las noticias en vivo, separados por comas (si no la creas, usa una lista por defecto: Fed, FOMC, Powell, ECB, BoE, BoJ, CPI, PCE, NFP, GDP, PMI, tarifas, etc.)
5. **Actions → ForexFactory alerts → Run workflow**.

La primera ejecución solo memoriza las noticias existentes; a partir de ahí te llegan las nuevas.

---

## Parte 2 — Mac (FF News con color exacto)

1. Abre **Terminal** (Cmd + Espacio → "Terminal").
2. Escribe `cd ` (con espacio), arrastra la carpeta `mac-ff-news` a la ventana y pulsa Enter.
3. Ejecuta, con tu tema:
   ```
   bash instalar.sh TU_TEMA_NTFY
   ```
4. Tarda 2–3 minutos. Al terminar queda corriendo en segundo plano y se inicia solo cada vez que entras al Mac.

Revisa ForexFactory /news cada 60 segundos. Mientras está activo, evita que el Mac se duerma por inactividad, pero **si cierras la tapa del portátil se detiene** hasta que lo vuelvas a abrir.

- Ver qué está haciendo: `tail -f ~/.ff-alerts/log.txt`
- Si ForexFactory lo bloquea en modo oculto, abrirá una ventana de Chrome visible automáticamente; déjala abierta (puedes minimizarla).
- Si te llega el aviso "⚠️ No encuentro noticias", ForexFactory cambió su página: mándame `~/.ff-alerts/debug.png`.
- Para quitarlo: `bash desinstalar.sh`
