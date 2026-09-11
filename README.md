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

V `scripts/cyclades_catalog.sql` jsou připravené read-only dotazy pro zdroj SUIVPRO: stroje z `MACHINE` a vstřikovací formy z živého pohledu `LISTE_OUTILS` (prefix `MO`). Aplikace začíná na malé demo sadě, aby fungovala bez přístupu do Cyclades. Další krok je spouštět import těchto dvou výsledků z dostupné `spc-vm` do lokální SQLite databáze, například jednou denně.

## Produkční nasazení Ubuntu

Nech aplikaci běžet na jednom Gunicorn workeru (SQLite má jednoho zapisujícího klienta). Před ní nasadit Caddy pro HTTPS. Pro tento rozsah je SQLite/WAL vhodná; při rozšíření na více závodů lze databázi nahradit PostgreSQL.
