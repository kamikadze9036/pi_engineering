# ProcessLog — procesní deník vstřikovny

Jednoduchá interní aplikace pro denní zápis procesních změn technologů. Technolog se přihlásí firemním SSO (Authentik), vybere stroj a nástroj přes našeptávač a doplní změněné parametry. Admin vidí kompletní historii, multisearch a lokální číselníky.

## Rychlé spuštění přes Docker Desktop

```bash
cp .env.example .env
docker compose up --build
```

Otevři `http://localhost:8000`.

## Přihlášení / SSO (Authentik)

Aplikace **nemá vlastní přihlašovací stránku ani hesla**. Před ní stojí Caddy s forward auth na
Authentik (repo `pi_caddy`); po přihlášení Caddy předává hlavičky `X-Authentik-Username`,
`X-Authentik-Groups` (oddělovač `|`) a `X-Authentik-Name`. Aplikace z nich při každém requestu:

- najde uživatele podle **stejného username** (historie změn a audit zůstávají u stejného účtu),
  neznámého založí (jméno z `X-Authentik-Name`);
- nastaví roli podle skupin:

| Skupina Authentik | Role v ProcessLogu |
| --- | --- |
| `spc-admin` nebo `processlog-admin` | Admin |
| `processlog-technolog` | Technolog |
| žádná z nich | přístup odepřen (stránka s vysvětlením) |

Správa → Uživatelé umí účet jen lokálně deaktivovat; jména, hesla a role se mění v Authentiku.
Odhlásit = přesměrování na `/outpost.goauthentik.io/sign_out`.

**Bezpečnostní podmínka:** kontejner nesmí publikovat port přímo na hostu, jinak jde hlavičky
podvrhnout. Za proxy to řeší `scripts/enable-app.sh processlog` v `pi_caddy`.

**Migrace stávajících účtů** (na VM, v kontejneru):

```bash
docker compose exec processlog python scripts/sso_users.py list              # kdo tu je
docker compose exec processlog python scripts/sso_users.py rename technik jnovak   # username = login v Authentiku
docker compose exec processlog python scripts/sso_users.py drop-passwords --yes    # až SSO funguje
```

**Povinný `.env`** vedle `compose.yml` se `SECRET_KEY` (viz `.env.example`); bez něj kontejner
nenastartuje. Výchozí účty `admin`/`technik` se už nezakládají.

**Lokální vývoj bez Authentiku:** `FLASK_DEBUG=1 SSO_DEV_USER=admin` (volitelně
`SSO_DEV_GROUPS=spc-users|processlog-technolog`), viz `.env.example`. Testy posílají hlavičky přímo.

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
