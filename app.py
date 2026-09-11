import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


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
              material TEXT, active INTEGER NOT NULL DEFAULT 1, source TEXT NOT NULL DEFAULT 'local'
            );
            CREATE TABLE IF NOT EXISTS process_changes (
              id INTEGER PRIMARY KEY, changed_at TEXT NOT NULL, user_id INTEGER NOT NULL,
              machine_id INTEGER NOT NULL, tool_id INTEGER NOT NULL, product_material TEXT,
              parameter_name TEXT, old_value TEXT, new_value TEXT, description TEXT NOT NULL,
              result_status TEXT NOT NULL CHECK(result_status IN ('confirmed','pending','reverted')),
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(machine_id) REFERENCES machines(id),
              FOREIGN KEY(tool_id) REFERENCES tools(id)
            );
            CREATE INDEX IF NOT EXISTS idx_changes_changed_at ON process_changes(changed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_changes_machine ON process_changes(machine_id);
            CREATE INDEX IF NOT EXISTS idx_changes_tool ON process_changes(tool_id);
            """
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
        return {"current_user": current_user(), "status_labels": {"confirmed": "Potvrzeno", "pending": "Čeká na ověření", "reverted": "Vráceno zpět"}}

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

    @app.get("/")
    @login_required
    def dashboard():
        user = current_user()
        recent = get_db().execute(
            """SELECT c.*, u.display_name, m.code machine_code, m.name machine_name, t.code tool_code, t.name tool_name
               FROM process_changes c JOIN users u ON u.id=c.user_id JOIN machines m ON m.id=c.machine_id JOIN tools t ON t.id=c.tool_id
               WHERE c.user_id = ? ORDER BY c.changed_at DESC LIMIT 5""", (user["id"],)
        ).fetchall()
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
        if form["result_status"] not in ("confirmed", "pending", "reverted"):
            abort(400)
        db = get_db()
        machine = db.execute("SELECT id FROM machines WHERE id=? AND active=1", (form["machine_id"],)).fetchone()
        tool = db.execute("SELECT id FROM tools WHERE id=? AND active=1", (form["tool_id"],)).fetchone()
        if not machine or not tool:
            flash("Zvolený stroj nebo nástroj již není aktivní.", "error")
            return redirect(url_for("dashboard"))
        now = datetime.now().isoformat(timespec="seconds")
        db.execute(
            """INSERT INTO process_changes(changed_at,user_id,machine_id,tool_id,product_material,parameter_name,old_value,new_value,description,result_status,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (form["changed_at"], user["id"], form["machine_id"], form["tool_id"], form.get("product_material", "").strip(), form.get("parameter_name", "").strip(), form.get("old_value", "").strip(), form.get("new_value", "").strip(), form["description"].strip(), form["result_status"], now, now),
        )
        db.commit()
        flash("Procesní změna byla uložena.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/history")
    @login_required
    def history():
        user = current_user()
        q = request.args.get("q", "").strip()
        sql = """SELECT c.*,u.display_name,m.code machine_code,m.name machine_name,t.code tool_code,t.name tool_name
                 FROM process_changes c JOIN users u ON u.id=c.user_id JOIN machines m ON m.id=c.machine_id JOIN tools t ON t.id=c.tool_id WHERE 1=1"""
        params = []
        if user["role"] != "admin":
            sql += " AND c.user_id=?"; params.append(user["id"])
        if q:
            like = f"%{q}%"
            sql += " AND (m.code LIKE ? OR m.name LIKE ? OR t.code LIKE ? OR t.name LIKE ? OR u.display_name LIKE ? OR c.description LIKE ? OR c.parameter_name LIKE ? OR c.product_material LIKE ?)"
            params.extend([like] * 8)
        sql += " ORDER BY c.changed_at DESC LIMIT 300"
        changes = get_db().execute(sql, params).fetchall()
        return render_template("history.html", changes=changes, q=q)

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
