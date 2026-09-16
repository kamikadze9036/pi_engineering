# Technologické předpisy - první testovací verze

Samostatná aplikace vedle ProcessLogu. Ukládá technologické předpisy a revize do PostgreSQL, čte stroje/formy z read-only exportu Cyklades a vydává archivované PDF návodky. Schválená revize zůstává neměnná; další změna vzniká její kopií. Datový formulář a jednostránkový PDF export kopírují sekce, pořadí, opakované stupně a zóny z `U10_3045_ON_260728_900-002_Schwarz.pdf` (81 typů parametrů, 253 jednotlivých polí).

## Zítřejší offline test

V adresáři `specs`:

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

Otevřít `http://localhost:8081`. V testovacím režimu (`SPECS_DEMO_MODE=true`) jsou k dispozici jasně označené stroje `P-DEMO-*` a formy `MO-DEMO-*`. Účty:

| Účet | Role | Heslo v testovacím `.env` |
| --- | --- | --- |
| `inzenyr` | ENGINEER | hodnota `SPECS_DEMO_PASSWORD` |
| `schvalovatel` | APPROVER | hodnota `SPECS_DEMO_PASSWORD` |
| `admin` | ADMIN | hodnota `SPECS_ADMIN_PASSWORD` |

Test: přihlásit se jako `inzenyr`, vybrat stroj, formu a výchozí vzor. Součástí instalace je prázdná ENGEL návodka a referenční U10/3045 s hodnotami z dodaného PDF. Nový draft dostane hodnoty, pozice i tolerance ze vzoru; formulář pak lze upravit po sekcích. Prázdná pole lze nechat prázdná. Doplnit důvod a změny, uložit draft a odeslat. Přihlásit se jako `schvalovatel`, schválit revizi a použít **Vydat / otevřít PDF**. Aktuální schválenou revizi může inženýr nebo administrátor uložit pod vlastním názvem jako další neměnný vzor pro nové nástroje. Nová revize stejného předpisu dál vzniká kopií platné revize. Admin může publikovat další verzi vzhledu PDF; již vydané PDF zůstává archivované.

Data jsou ve volumes `specs_pgdata` a `specs_pdf`. Běžné `docker compose down` je nesmaže. Nepoužívat `down -v`, pokud má historie zůstat zachovaná.

## Ubuntu a Cyklades po návratu do firemní sítě

1. Na Ubuntu hostiteli zprovoznit stejný SSH alias `spc-vm` a oprávnění k Docker/sqlcmd na cílové VM jako pro současný `scripts/sync_cyclades.py`. Heslo do MES zůstává v `~/cyclades-db.env` na `spc-vm`.
2. Z kořene repozitáře nejdřív spustit `python3 specs/export_cyclades.py --dry-run`. Poté `python3 specs/export_cyclades.py`; vznikne atomický soubor `specs/mes-export/catalog.json`.
3. V `specs/.env` přepnout `SPECS_DEMO_MODE=false` a `SPECS_MES_CATALOG_PATH=/data/mes/catalog.json`, změnit všechna testovací hesla/secrets, potom `docker compose up --build -d` v `specs`. Pro první interní test lze nastavit `SPECS_BOOTSTRAP_TEST_USERS=true`; tím zůstanou aktivní oddělené účty `inzenyr` a `schvalovatel` i nad reálným MES číselníkem. Po založení skutečných uživatelů tuto volbu vypnout.
4. Spouštět export periodicky na hostiteli (například denně). Aplikace odmítne zakládat/schvalovat nové revize, pokud je export starší než 36 hodin; již schválené hodnoty/PDF zůstávají čitelné.

**Před převodem skutečných předpisů ověřit**, zda `MAC_REFMAC` a `OUT_REFOUT` jsou trvalé identifikátory MES a zda existuje zdroj platných kombinací stroj–forma. Aktuální export používá kódy, stejně jako ProcessLog; živé SQL schéma zatím nebylo možné ověřit bez firemní sítě. Nová databáze stroje ani formy ručně neudržuje.

## Provozní poznámky

- Vnitřní API není publikované samostatným portem; Nginx obsluhuje UI a proxy `/api/v1` na backend. Pro provoz mimo lokální test použít firemní HTTPS/reverse proxy a `SPECS_COOKIE_SECURE=true`.
- `specs-init` při startu provede verzované migrace Alembic a idempotentní založení první administrace/katalogu. Změny schématu se přidávají jako další migrace, nikoli přepisem historických revizí.
- Výchozí procesní vzory jsou neměnné snapshoty. Dva systémové vzory vytváří seed; další vzniknou pouze z aktuální schválené revize a zobrazí se ve výběru při založení nového předpisu.
- PDF při prvním vydání uloží soubor, verzi šablony a SHA-256 do databáze; další otevření používá přesně tentýž soubor. Zálohovat **PostgreSQL i PDF volume** společně.
- Admin editor vzhledu v MVP ovládá základní styl. Pro budoucí úplnou úpravu rozložení je připravená verzovaná tabulka `pdf_templates.settings`; po rozboru dalších návodek lze doplnit editaci sekcí, polí, loga a šablon podle typu stroje.

## Lokální vývoj bez Dockeru

Z `specs/backend`: vytvořit venv, nainstalovat `requirements.txt`, nastavit `SPECS_ADMIN_PASSWORD` a `SPECS_DEMO_MODE=true`, spustit `alembic upgrade head`, `python -m app.seed`, `uvicorn app.main:app --port 8001`. V `specs/frontend`: `npm ci`, `npm run dev`; Vite proxy směruje API na port 8001. Backend test: `python -m pytest -q tests/test_workflow.py` (testovací závislosti `httpx` a `pytest`).
