# ProcessLog — procesní deník vstřikovny

Jednoduchá interní aplikace pro denní zápis procesních změn technologů. Technolog se přihlásí, vybere stroj a nástroj přes našeptávač a doplní změněné parametry. Admin vidí kompletní historii, multisearch a lokální číselníky.

## Rychlé spuštění přes Docker Desktop

```bash
cp .env.example .env
docker compose up --build
```

Otevři `http://localhost:8000`.

| Role | Uživatelské jméno | Heslo |
| --- | --- | --- |
| Admin | `admin` | `admin123` |
| Technolog | `technik` | `technik123` |

Výchozí hesla jsou pouze pro prototyp. Před skutečným nasazením nastav silný `SECRET_KEY`, změň výchozí hesla a aplikaci provozuj přes HTTPS s `SESSION_COOKIE_SECURE=true`.

Databáze SQLite je uložena v Docker volume `processlog_data`; `docker compose down` ji nesmaže. Záloha databáze:

```bash
docker compose exec processlog sh -c 'cp /data/processlog.db /data/processlog-backup.db'
```

## Cyclades číselníky

V `scripts/cyclades_catalog.sql` jsou připravené read-only dotazy pro zdroj SUIVPRO: vstřikovací lisy z `MACHINE` (reference `P…`) a vstřikovací formy z živého pohledu `LISTE_OUTILS` (prefix `MO`). Synchronizace používá existující bezpečné přihlášení `spc-vm` a soubor `~/cyclades-db.env` na této VM — heslo se nekopíruje do aplikace ani repozitáře.

Po spuštění aplikace načti reálný číselník z hostitele Dockeru:

```bash
python3 scripts/sync_cyclades.py
```

Na samotné `spc-vm` spusť přímý režim (bez SSH na sebe sama):

```bash
python3 scripts/sync_cyclades.py --ssh-target local
```

Kontrola zdroje bez zápisu do SQLite:

```bash
python3 scripts/sync_cyclades.py --dry-run
```

Pro denní synchronizaci přidej na Ubuntu například cron v 02:30:

```cron
30 2 * * * cd /opt/processlog && /usr/bin/python3 scripts/sync_cyclades.py >> /var/log/processlog-sync.log 2>&1
```

Synchronizace deaktivuje pouze staré položky dříve načtené z Cyclades (a demo data); položky doplněné adminem zůstávají zachované.

## Produkční nasazení Ubuntu

Nech aplikaci běžet na jednom Gunicorn workeru (SQLite má jednoho zapisujícího klienta). Před ní nasadit Caddy pro HTTPS. Pro tento rozsah je SQLite/WAL vhodná; při rozšíření na více závodů lze databázi nahradit PostgreSQL.
