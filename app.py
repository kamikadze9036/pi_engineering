import os
import json
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESS_CHANGE_STATUSES = ("confirmed", "pending", "reverted", "test_verified_reverted")
STATUS_LABELS = {
    "confirmed": "Potvrzeno",
    "pending": "Čeká na ověření",
    "reverted": "Vráceno zpět",
    "test_verified_reverted": "Test ověřen OK — vráceno zpět",
}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-before-production"),
        DATABASE=os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "data", "processlog.db")),
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
    )
    if test_config:
        app.config.update(test_config)

    def connect_db():
        os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
        connection = sqlite3.connect(app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def get_db():
        if "db" not in g:
            g.db = connect_db()
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        db = connect_db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
              display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('admin','technolog')),
              active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS machines (
              id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
              location TEXT, active INTEGER NOT NULL DEFAULT 1, source TEXT NOT NULL DEFAULT 'local'
            );
            CREATE TABLE IF NOT EXISTS tools (
              id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
              material TEXT, active INTEGER NOT NULL DEFAULT 1, source TEXT NOT NULL DEFAULT 'local',
              active_override INTEGER CHECK(active_override IN (0,1))
            );
            CREATE TABLE IF NOT EXISTS process_changes (
              id INTEGER PRIMARY KEY, changed_at TEXT NOT NULL, user_id INTEGER NOT NULL,
              machine_id INTEGER NOT NULL, tool_id INTEGER NOT NULL, product_material TEXT,
              parameter_name TEXT, old_value TEXT, new_value TEXT, description TEXT NOT NULL,
              result_status TEXT NOT NULL CHECK(result_status IN ('confirmed','pending','reverted','test_verified_reverted')),
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(machine_id) REFERENCES machines(id),
              FOREIGN KEY(tool_id) REFERENCES tools(id)
            );
            CREATE INDEX IF NOT EXISTS idx_changes_changed_at ON process_changes(changed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_changes_machine ON process_changes(machine_id);
            CREATE INDEX IF NOT EXISTS idx_changes_tool ON process_changes(tool_id);
            """
        )
        tool_columns = {row["name"] for row in db.execute("PRAGMA table_info(tools)").fetchall()}
        if "active_override" not in tool_columns:
            db.execute("ALTER TABLE tools ADD COLUMN active_override INTEGER CHECK(active_override IN (0,1))")
        process_changes_sql = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='process_changes'"
        ).fetchone()["sql"]
        if "test_verified_reverted" not in process_changes_sql:
            # SQLite neumí upravit CHECK omezení tabulky. Při aktualizaci starší
            # databáze proto tabulku bezpečně vytvoříme znovu a zachováme data.
            db.executescript(
                """
                DROP INDEX IF EXISTS idx_changes_changed_at;
                DROP INDEX IF EXISTS idx_changes_machine;
                DROP INDEX IF EXISTS idx_changes_tool;
                ALTER TABLE process_changes RENAME TO process_changes_legacy;
                CREATE TABLE process_changes (
                  id INTEGER PRIMARY KEY, changed_at TEXT NOT NULL, user_id INTEGER NOT NULL,
                  machine_id INTEGER NOT NULL, tool_id INTEGER NOT NULL, product_material TEXT,
                  parameter_name TEXT, old_value TEXT, new_value TEXT, description TEXT NOT NULL,
                  result_status TEXT NOT NULL CHECK(result_status IN ('confirmed','pending','reverted','test_verified_reverted')),
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(machine_id) REFERENCES machines(id),
                  FOREIGN KEY(tool_id) REFERENCES tools(id)
                );
                INSERT INTO process_changes(id,changed_at,user_id,machine_id,tool_id,product_material,parameter_name,old_value,new_value,description,result_status,created_at,updated_at)
                  SELECT id,changed_at,user_id,machine_id,tool_id,product_material,parameter_name,old_value,new_value,description,result_status,created_at,updated_at
                  FROM process_changes_legacy;
                DROP TABLE process_changes_legacy;
                CREATE INDEX idx_changes_changed_at ON process_changes(changed_at DESC);
                CREATE INDEX idx_changes_machine ON process_changes(machine_id);
                CREATE INDEX idx_changes_tool ON process_changes(tool_id);
                """
            )
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS change_parameters (
              id INTEGER PRIMARY KEY, change_id INTEGER NOT NULL, position INTEGER NOT NULL,
              parameter_name TEXT NOT NULL, old_value TEXT, new_value TEXT,
              FOREIGN KEY(change_id) REFERENCES process_changes(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_change_parameters_change ON change_parameters(change_id, position);
            CREATE TABLE IF NOT EXISTS change_audit (
              id INTEGER PRIMARY KEY, change_id INTEGER NOT NULL, edited_at TEXT NOT NULL,
              editor_id INTEGER NOT NULL, action TEXT NOT NULL CHECK(action IN ('created','updated')),
              details TEXT NOT NULL DEFAULT '{}',
              FOREIGN KEY(change_id) REFERENCES process_changes(id) ON DELETE CASCADE,
              FOREIGN KEY(editor_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_change_audit_change ON change_audit(change_id, edited_at DESC);
            """
        )
        # Dosavadní jeden parametr na změně přeneseme do nové podřízené tabulky.
        # Původní sloupce ponecháváme kvůli bezpečné zpětné kompatibilitě migrace.
        db.execute(
            """INSERT INTO change_parameters(change_id, position, parameter_name, old_value, new_value)
               SELECT c.id, 1, c.parameter_name, c.old_value, c.new_value
               FROM process_changes c
               WHERE TRIM(COALESCE(c.parameter_name, '')) <> ''
                 AND NOT EXISTS (SELECT 1 FROM change_parameters p WHERE p.change_id = c.id)"""
        )
        db.execute(
            """INSERT INTO change_audit(change_id, edited_at, editor_id, action, details)
               SELECT c.id, c.created_at, c.user_id, 'created', '{"summary":["Původní záznam"]}'
               FROM process_changes c
               WHERE NOT EXISTS (SELECT 1 FROM change_audit a WHERE a.change_id = c.id)"""
        )
        now = datetime.now().isoformat(timespec="seconds")
        if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            db.executemany(
                "INSERT INTO users(username, display_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                [
                    ("admin", "Petr Novák", generate_password_hash("admin123"), "admin", now),
                    ("technik", "Jan Svoboda", generate_password_hash("technik123"), "technolog", now),
                ],
            )
        if not db.execute("SELECT 1 FROM machines LIMIT 1").fetchone():
            db.executemany(
                "INSERT INTO machines(code, name, location, source) VALUES (?, ?, ?, 'demo')",
                [("1100-03", "Arburg 570S", "Lisovna 2"), ("1200-01", "Engel Victory 120", "Lisovna 1"), ("1600-02", "KraussMaffei CX 160", "Lisovna 3")],
            )
        if not db.execute("SELECT 1 FROM tools LIMIT 1").fetchone():
            db.executemany(
                "INSERT INTO tools(code, name, material, source) VALUES (?, ?, ?, 'demo')",
                [("MO2945", "DOOR PANEL BR214", "PP talc"), ("MO3480", "DOOR PANEL X244", "PP talc"), ("MO2989", "DOOR PANEL BR177", "ABS"), ("MO2944", "DOOR PANEL BR206", "ABS")],
            )
        db.commit()
        db.close()

    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        return get_db().execute("SELECT * FROM users WHERE id = ? AND active = 1", (user_id,)).fetchone()

    @app.context_processor
    def template_context():
        return {"current_user": current_user(), "status_labels": STATUS_LABELS}

    def attach_parameters(db, changes):
        """Připojí parametry k událostem změny pro výpis i fulltextové hledání."""
        if not changes:
            return changes
        by_change_id = {change["id"]: change for change in changes}
        for change in changes:
            change["parameters"] = []
        placeholders = ",".join("?" for _ in by_change_id)
        rows = db.execute(
            f"""SELECT change_id, parameter_name, old_value, new_value
                FROM change_parameters WHERE change_id IN ({placeholders})
                ORDER BY change_id, position, id""",
            tuple(by_change_id),
        ).fetchall()
        for row in rows:
            parameter = dict(row)
            by_change_id[parameter.pop("change_id")]["parameters"].append(parameter)
        for change in changes:
            change["parameter_search"] = " ".join(
                " ".join(filter(None, (parameter["parameter_name"], parameter["old_value"], parameter["new_value"])))
                for parameter in change["parameters"]
            )
        return changes

    def get_change(db, change_id):
        row = db.execute(
            """SELECT c.*, u.display_name, m.code machine_code, m.name machine_name,
                      t.code tool_code, t.name tool_name
               FROM process_changes c JOIN users u ON u.id=c.user_id
               JOIN machines m ON m.id=c.machine_id JOIN tools t ON t.id=c.tool_id
               WHERE c.id=?""",
            (change_id,),
        ).fetchone()
        if not row:
            abort(404)
        change = dict(row)
        return attach_parameters(db, [change])[0]

    def change_snapshot(change):
        return {
            "product_material": change.get("product_material") or "",
            "description": change["description"],
            "result_status": change["result_status"],
            "parameters": [
                {"parameter_name": parameter["parameter_name"], "old_value": parameter["old_value"] or "", "new_value": parameter["new_value"] or ""}
                for parameter in change["parameters"]
            ],
        }

    def parameter_label(parameter):
        return f"{parameter['parameter_name']}: {parameter['old_value'] or '—'} → {parameter['new_value'] or '—'}"

    def summarize_update(before, after):
        summary = []
        if before["result_status"] != after["result_status"]:
            summary.append(f"Stav: {STATUS_LABELS[before['result_status']]} → {STATUS_LABELS[after['result_status']]}")
        if before["product_material"] != after["product_material"]:
            summary.append("Díl / materiál upraven")
        if before["description"] != after["description"]:
            summary.append("Popis změny upraven")
        before_parameters, after_parameters = before["parameters"], after["parameters"]
        for index in range(max(len(before_parameters), len(after_parameters))):
            old = before_parameters[index] if index < len(before_parameters) else None
            new = after_parameters[index] if index < len(after_parameters) else None
            if old == new:
                continue
            if old is None:
                summary.append(f"Přidán parametr: {parameter_label(new)}")
            elif new is None:
                summary.append(f"Odebrán parametr: {parameter_label(old)}")
            else:
                summary.append(f"Parametr upraven: {parameter_label(old)} → {parameter_label(new)}")
        return summary

    def add_audit_entry(db, change_id, editor_id, action, before, after):
        details = {
            "before": before,
            "after": after,
            "summary": ["Záznam vytvořen"] if action == "created" else summarize_update(before, after),
        }
        db.execute(
            "INSERT INTO change_audit(change_id,edited_at,editor_id,action,details) VALUES(?,?,?,?,?)",
            (change_id, datetime.now().isoformat(timespec="seconds"), editor_id, action, json.dumps(details, ensure_ascii=False)),
        )

    def get_audit_entries(db, change_id):
        entries = [dict(row) for row in db.execute(
            """SELECT a.*, u.display_name FROM change_audit a JOIN users u ON u.id=a.editor_id
               WHERE a.change_id=? ORDER BY a.edited_at DESC, a.id DESC""",
            (change_id,),
        ).fetchall()]
        for entry in entries:
            details = json.loads(entry["details"])
            entry["summary"] = details.get("summary", [])
        return entries

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user() is None:
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for("login"))
            if user["role"] != "admin":
                abort(403)
            return view(*args, **kwargs)
        return wrapped

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user():
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            user = get_db().execute("SELECT * FROM users WHERE username = ? AND active = 1", (username,)).fetchone()
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session.permanent = True
                session["user_id"] = user["id"]
                return redirect(request.args.get("next") or url_for("dashboard"))
            flash("Nesprávné uživatelské jméno nebo heslo.", "error")
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/account/password", methods=["GET", "POST"])
    @login_required
    def change_password():
        user = current_user()
        if request.method == "POST":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirmation = request.form.get("confirmation", "")
            if not check_password_hash(user["password_hash"], current_password):
                flash("Současné heslo nesouhlasí.", "error")
            elif len(new_password) < 8:
                flash("Nové heslo musí mít alespoň 8 znaků.", "error")
            elif new_password != confirmation:
                flash("Nové heslo a potvrzení se neshodují.", "error")
            else:
                get_db().execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), user["id"]))
                get_db().commit()
                flash("Heslo bylo změněno.", "success")
                return redirect(url_for("dashboard"))
        return render_template("change_password.html")

    @app.get("/")
    @login_required
    def dashboard():
        user = current_user()
        db = get_db()
        recent = [dict(row) for row in db.execute(
            """SELECT c.*, u.display_name, m.code machine_code, m.name machine_name, t.code tool_code, t.name tool_name
               FROM process_changes c JOIN users u ON u.id=c.user_id JOIN machines m ON m.id=c.machine_id JOIN tools t ON t.id=c.tool_id
               WHERE c.user_id = ? ORDER BY c.changed_at DESC LIMIT 5""", (user["id"],)
        ).fetchall()]
        attach_parameters(db, recent)
        return render_template("dashboard.html", recent=recent, now=datetime.now().strftime("%Y-%m-%dT%H:%M"))

    @app.post("/changes")
    @login_required
    def create_change():
        user = current_user()
        form = request.form
        required = ("machine_id", "tool_id", "description", "result_status", "changed_at")
        if any(not form.get(field, "").strip() for field in required):
            flash("Vyplň stroj, nástroj, popis, stav a čas změny.", "error")
            return redirect(url_for("dashboard"))
        if form["result_status"] not in PROCESS_CHANGE_STATUSES:
            abort(400)
        parameter_names = form.getlist("parameter_name")
        old_values = form.getlist("old_value")
        new_values = form.getlist("new_value")
        parameters = []
        for position in range(max(len(parameter_names), len(old_values), len(new_values))):
            name = parameter_names[position].strip() if position < len(parameter_names) else ""
            old_value = old_values[position].strip() if position < len(old_values) else ""
            new_value = new_values[position].strip() if position < len(new_values) else ""
            if not any((name, old_value, new_value)):
                continue
            if not name:
                flash("U každého vyplněného řádku uveď název parametru.", "error")
                return redirect(url_for("dashboard"))
            parameters.append((position + 1, name, old_value, new_value))
        db = get_db()
        machine = db.execute("SELECT id FROM machines WHERE id=? AND active=1", (form["machine_id"],)).fetchone()
        tool = db.execute("SELECT id FROM tools WHERE id=? AND active=1", (form["tool_id"],)).fetchone()
        if not machine or not tool:
            flash("Zvolený stroj nebo nástroj již není aktivní.", "error")
            return redirect(url_for("dashboard"))
        now = datetime.now().isoformat(timespec="seconds")
        cursor = db.execute(
            """INSERT INTO process_changes(changed_at,user_id,machine_id,tool_id,product_material,description,result_status,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (form["changed_at"], user["id"], form["machine_id"], form["tool_id"], form.get("product_material", "").strip(), form["description"].strip(), form["result_status"], now, now),
        )
        db.executemany(
            """INSERT INTO change_parameters(change_id, position, parameter_name, old_value, new_value)
               VALUES(?,?,?,?,?)""",
            [(cursor.lastrowid, position, name, old_value, new_value) for position, name, old_value, new_value in parameters],
        )
        new_snapshot = {
            "product_material": form.get("product_material", "").strip(),
            "description": form["description"].strip(),
            "result_status": form["result_status"],
            "parameters": [
                {"parameter_name": name, "old_value": old_value, "new_value": new_value}
                for _position, name, old_value, new_value in parameters
            ],
        }
        add_audit_entry(db, cursor.lastrowid, user["id"], "created", None, new_snapshot)
        db.commit()
        flash("Procesní změna byla uložena.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/changes/<int:change_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_change(change_id):
        db = get_db()
        user = current_user()
        change = get_change(db, change_id)
        if change["user_id"] != user["id"] and user["role"] != "admin":
            abort(403)
        if request.method == "POST":
            result_status = request.form.get("result_status", "")
            if result_status not in PROCESS_CHANGE_STATUSES:
                abort(400)
            description = request.form.get("description", "").strip()
            if not description:
                flash("Popis změny je povinný.", "error")
                return redirect(url_for("edit_change", change_id=change_id))
            parameter_names = request.form.getlist("parameter_name")
            old_values = request.form.getlist("old_value")
            new_values = request.form.getlist("new_value")
            parameters = []
            for position in range(max(len(parameter_names), len(old_values), len(new_values))):
                name = parameter_names[position].strip() if position < len(parameter_names) else ""
                old_value = old_values[position].strip() if position < len(old_values) else ""
                new_value = new_values[position].strip() if position < len(new_values) else ""
                if not any((name, old_value, new_value)):
                    continue
                if not name:
                    flash("U každého vyplněného řádku uveď název parametru.", "error")
                    return redirect(url_for("edit_change", change_id=change_id))
                parameters.append((position + 1, name, old_value, new_value))
            before = change_snapshot(change)
            after = {
                "product_material": request.form.get("product_material", "").strip(),
                "description": description,
                "result_status": result_status,
                "parameters": [
                    {"parameter_name": name, "old_value": old_value, "new_value": new_value}
                    for _position, name, old_value, new_value in parameters
                ],
            }
            if before == after:
                flash("Nejsou zde žádné nové úpravy k uložení.", "error")
                return redirect(url_for("edit_change", change_id=change_id))
            db.execute(
                """UPDATE process_changes SET product_material=?, description=?, result_status=?, updated_at=?
                   WHERE id=?""",
                (after["product_material"], after["description"], after["result_status"], datetime.now().isoformat(timespec="seconds"), change_id),
            )
            db.execute("DELETE FROM change_parameters WHERE change_id=?", (change_id,))
            db.executemany(
                """INSERT INTO change_parameters(change_id, position, parameter_name, old_value, new_value)
                   VALUES(?,?,?,?,?)""",
                [(change_id, position, name, old_value, new_value) for position, name, old_value, new_value in parameters],
            )
            add_audit_entry(db, change_id, user["id"], "updated", before, after)
            db.commit()
            flash("Procesní změna byla doplněna. Historie úprav je uložená.", "success")
            return redirect(url_for("edit_change", change_id=change_id))
        return render_template("edit_change.html", change=change, audit_entries=get_audit_entries(db, change_id))

    @app.get("/changes/<int:change_id>/timeline")
    @login_required
    def change_timeline(change_id):
        db = get_db()
        change = get_change(db, change_id)
        return render_template("change_timeline.html", change=change, audit_entries=get_audit_entries(db, change_id))

    @app.get("/history")
    @login_required
    def history():
        user = current_user()
        q = request.args.get("q", "").strip()
        sql = """SELECT c.*,u.display_name,m.code machine_code,m.name machine_name,t.code tool_code,t.name tool_name
                 FROM process_changes c JOIN users u ON u.id=c.user_id JOIN machines m ON m.id=c.machine_id JOIN tools t ON t.id=c.tool_id WHERE 1=1"""
        params = []
        sql += " ORDER BY c.changed_at DESC LIMIT 300"
        db = get_db()
        changes = [dict(row) for row in db.execute(sql, params).fetchall()]
        attach_parameters(db, changes)
        return render_template("history.html", changes=changes, q=q)

    @app.post("/history/<int:change_id>/delete")
    @admin_required
    def delete_change(change_id):
        change = get_db().execute("SELECT id FROM process_changes WHERE id=?", (change_id,)).fetchone()
        if not change:
            abort(404)
        get_db().execute("DELETE FROM process_changes WHERE id=?", (change_id,))
        get_db().commit()
        flash("Záznam v historii byl smazán.", "success")
        return redirect(url_for("history", q=request.form.get("q", "")))

    @app.get("/api/catalog/machines")
    @login_required
    def machine_suggestions():
        q = request.args.get("q", "").strip()
        like = f"%{q}%"
        rows = get_db().execute("SELECT id,code,name,location FROM machines WHERE active=1 AND (code LIKE ? OR name LIKE ? OR COALESCE(location,'') LIKE ?) ORDER BY code LIMIT 12", (like, like, like)).fetchall()
        return jsonify([dict(row) for row in rows])

    @app.get("/api/catalog/tools")
    @login_required
    def tool_suggestions():
        q = request.args.get("q", "").strip()
        like = f"%{q}%"
        rows = get_db().execute("SELECT id,code,name,material FROM tools WHERE active=1 AND (code LIKE ? OR name LIKE ? OR COALESCE(material,'') LIKE ?) ORDER BY code LIMIT 12", (like, like, like)).fetchall()
        return jsonify([dict(row) for row in rows])

    @app.get("/admin")
    @admin_required
    def admin():
        db = get_db()
        stats = {"changes": db.execute("SELECT COUNT(*) FROM process_changes").fetchone()[0], "pending": db.execute("SELECT COUNT(*) FROM process_changes WHERE result_status='pending'").fetchone()[0], "tools": db.execute("SELECT COUNT(*) FROM tools WHERE active=1").fetchone()[0]}
        return render_template("admin.html", stats=stats, users=db.execute("SELECT * FROM users ORDER BY display_name").fetchall(), machines=db.execute("SELECT * FROM machines ORDER BY code LIMIT 100").fetchall(), tools=db.execute("SELECT * FROM tools ORDER BY code LIMIT 100").fetchall())

    @app.post("/admin/users")
    @admin_required
    def add_user():
        username = request.form.get("username", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "technolog")
        if not username or not display_name or len(password) < 4 or role not in ("admin", "technolog"):
            flash("Vyplň přihlašovací jméno, celé jméno, roli a heslo o délce alespoň 4 znaky.", "error")
            return redirect(url_for("admin"))
        try:
            get_db().execute("INSERT INTO users(username,display_name,password_hash,role,created_at) VALUES(?,?,?,?,?)", (username, display_name, generate_password_hash(password), role, datetime.now().isoformat(timespec="seconds")))
            get_db().commit()
            flash("Uživatel byl vytvořen.", "success")
        except sqlite3.IntegrityError:
            flash("Toto přihlašovací jméno už existuje.", "error")
        return redirect(url_for("admin"))

    @app.post("/admin/users/<int:user_id>")
    @admin_required
    def update_user(user_id):
        db = get_db()
        target = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not target:
            abort(404)
        display_name = request.form.get("display_name", "").strip()
        role = request.form.get("role", "technolog")
        active = 1 if request.form.get("active") == "on" else 0
        password = request.form.get("password", "")
        if not display_name or role not in ("admin", "technolog"):
            flash("Jméno a platná role jsou povinné.", "error")
        elif target["id"] == current_user()["id"] and not active:
            flash("Nemůžeš deaktivovat vlastní účet.", "error")
        elif password and len(password) < 4:
            flash("Resetované heslo musí mít alespoň 4 znaky.", "error")
        else:
            if password:
                db.execute("UPDATE users SET display_name=?,role=?,active=?,password_hash=? WHERE id=?", (display_name, role, active, generate_password_hash(password), user_id))
            else:
                db.execute("UPDATE users SET display_name=?,role=?,active=? WHERE id=?", (display_name, role, active, user_id))
            db.commit()
            flash("Uživatel byl upraven." + (" Heslo bylo resetováno." if password else ""), "success")
        return redirect(url_for("admin"))

    @app.post("/admin/tools/<int:tool_id>/active")
    @admin_required
    def set_tool_active(tool_id):
        tool = get_db().execute("SELECT * FROM tools WHERE id=?", (tool_id,)).fetchone()
        if not tool:
            abort(404)
        action = request.form.get("action")
        if action == "deactivate":
            get_db().execute("UPDATE tools SET active=0,active_override=0 WHERE id=?", (tool_id,))
            message = f"Nástroj {tool['code']} byl deaktivován a synchronizace jej nebude znovu aktivovat."
        elif action == "activate":
            get_db().execute("UPDATE tools SET active=1,active_override=NULL WHERE id=?", (tool_id,))
            message = f"Nástroj {tool['code']} je znovu aktivní."
        else:
            abort(400)
        get_db().commit()
        flash(message, "success")
        return redirect(url_for("admin"))

    @app.post("/admin/catalog/<kind>")
    @admin_required
    def add_catalog_item(kind):
        if kind not in ("machines", "tools"):
            abort(404)
        code, name = request.form.get("code", "").strip(), request.form.get("name", "").strip()
        if not code or not name:
            flash("Kód a název jsou povinné.", "error")
            return redirect(url_for("admin"))
        try:
            if kind == "machines": get_db().execute("INSERT INTO machines(code,name,location) VALUES(?,?,?)", (code, name, request.form.get("extra", "").strip()))
            else: get_db().execute("INSERT INTO tools(code,name,material) VALUES(?,?,?)", (code, name, request.form.get("extra", "").strip()))
            get_db().commit(); flash("Položka číselníku byla přidána.", "success")
        except sqlite3.IntegrityError:
            flash("Položka s tímto kódem už existuje.", "error")
        return redirect(url_for("admin"))

    init_db()
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=os.environ.get("FLASK_DEBUG") == "1")
