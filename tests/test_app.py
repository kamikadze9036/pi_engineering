import os
import sqlite3
import tempfile
import unittest

os.environ.setdefault("SECRET_KEY", "test")  # app.py vytváří aplikaci už při importu

from app import create_app


class ProcessLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE": os.path.join(self.tmp.name, "test.db"), "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    # SSO: místo loginu se nastaví hlavičky, které za Caddy posílá Authentik
    ADMIN = ("admin", "spc-users|processlog-admin", "Petr Novák")
    TECHNIK = ("technik", "spc-users|processlog-technolog", "Jan Svoboda")

    def login(self, username="admin", password=None):
        who = {"admin": self.ADMIN, "technik": self.TECHNIK}[username]
        return self.as_user(*who)

    def as_user(self, username, groups, name=""):
        self.client.environ_base = {
            "HTTP_X_AUTHENTIK_USERNAME": username,
            "HTTP_X_AUTHENTIK_GROUPS": groups,
            "HTTP_X_AUTHENTIK_NAME": name,
        }
        return self.client.get("/")

    def logout(self):
        self.client.environ_base = {}

    def test_login_and_catalog_filtering(self):
        response = self.login()
        self.assertIn("Nová procesní změna".encode(), response.data)
        machines = self.client.get("/api/catalog/machines?q=arburg").get_json()
        tools = self.client.get("/api/catalog/tools?q=mo2945").get_json()
        self.assertEqual(machines[0]["code"], "1100-03")
        self.assertEqual(tools[0]["code"], "MO2945")

    def test_save_multiple_parameters_and_multisearch(self):
        self.login("technik", "technik123")
        machine = self.client.get("/api/catalog/machines?q=1100").get_json()[0]
        tool = self.client.get("/api/catalog/tools?q=MO2945").get_json()[0]
        response = self.client.post("/changes", data={"changed_at":"2026-09-11T09:00","machine_id":machine["id"],"tool_id":tool["id"],"description":"Dotlak a bod přepnutí upraveny kvůli propadu.","result_status":"pending","parameter_name":["Dotlak", "Bod přepnutí"],"old_value":["420 bar", "12 mm"],"new_value":["455 bar", "10 mm"]}, follow_redirects=True)
        self.assertIn("Procesní změna byla uložena".encode(), response.data)
        history = self.client.get("/history?q=Bod přepnutí")
        self.assertIn("Dotlak a bod přepnutí upraveny".encode(), history.data)
        with sqlite3.connect(os.path.join(self.tmp.name, "test.db")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM change_parameters").fetchone()[0], 2)

    def test_verified_test_reverted_status_is_saved_and_labeled(self):
        self.login("technik", "technik123")
        response = self.client.post("/changes", data={"changed_at":"2026-09-11T09:00","machine_id":1,"tool_id":1,"description":"Ověřovací test vstřiku, nastavení bylo vráceno.","result_status":"test_verified_reverted"}, follow_redirects=True)
        self.assertIn("Procesní změna byla uložena".encode(), response.data)
        history = self.client.get("/history")
        self.assertIn("Test ověřen OK — vráceno zpět".encode(), history.data)

    def test_author_can_complete_change_and_see_audit_history(self):
        self.login("technik", "technik123")
        self.client.post("/changes", data={"changed_at":"2026-09-11T09:00","machine_id":1,"tool_id":1,"description":"Čeká na potvrzení kvalitou.","result_status":"pending","parameter_name":"Dotlak","old_value":"420 bar","new_value":"455 bar"})
        response = self.client.post("/changes/1/edit", data={"product_material":"PP talc","description":"Kvalita změnu odsouhlasila.","result_status":"confirmed","parameter_name":["Dotlak", "Bod přepnutí"],"old_value":["420 bar", "12 mm"],"new_value":["455 bar", "10 mm"]}, follow_redirects=True)
        self.assertIn("Historie úprav je uložená".encode(), response.data)
        timeline = self.client.get("/changes/1/timeline")
        self.assertIn("Stav: Čeká na ověření → Potvrzeno".encode(), timeline.data)
        self.assertIn("Přidán parametr: Bod přepnutí".encode(), timeline.data)
        with sqlite3.connect(os.path.join(self.tmp.name, "test.db")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM change_audit WHERE change_id=1").fetchone()[0], 2)

    def test_admin_can_deactivate_user_and_tool(self):
        self.login("technik")  # technik se založí při prvním přihlášení
        self.login()
        response = self.client.post("/admin/users/1", data={"active": "on"}, follow_redirects=True)
        self.assertIn("aktivován".encode(), response.data)
        self.client.post("/admin/users/1", data={}, follow_redirects=True)
        response = self.as_user(*self.TECHNIK)  # technik (id 1) deaktivován, i s platnou hlavičkou
        self.assertEqual(response.status_code, 403)
        self.assertIn("deaktivovaný".encode(), response.data)
        self.login()
        self.client.post("/admin/tools/1/active", data={"action": "deactivate"})
        self.assertEqual(self.client.get("/api/catalog/tools?q=MO2945").get_json(), [])

    def test_history_is_shared_but_only_admin_can_delete(self):
        self.login()
        self.client.post("/changes", data={"changed_at":"2026-09-11T09:00","machine_id":1,"tool_id":1,"description":"Adminův společný záznam.","result_status":"confirmed"})
        self.logout()
        self.login("technik", "technik123")
        self.assertIn("Adminův společný záznam".encode(), self.client.get("/history").data)
        self.assertEqual(self.client.post("/history/1/delete").status_code, 403)
        self.assertEqual(self.client.get("/changes/1/edit").status_code, 403)
        self.logout()
        self.login()
        response = self.client.post("/history/1/delete", follow_redirects=True)
        self.assertIn("Záznam v historii byl smazán".encode(), response.data)


if __name__ == "__main__":
    unittest.main()

    def test_sso_headers_create_user_and_map_roles(self):
        self.assertEqual(self.client.get("/").status_code, 403)  # bez hlaviček (mimo proxy)
        self.assertEqual(self.as_user("novak", "spc-users").status_code, 403)  # bez skupiny processlog-*
        self.assertIn("processlog-technolog".encode(), self.client.get("/").data)
        # jméno tak, jak ho WSGI opravdu předá (UTF-8 bajty dekódované jako latin-1)
        response = self.as_user("Novak", "spc-users|processlog-technolog", "Jan Novák".encode("utf-8").decode("latin-1"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Jan Novák".encode(), response.data)
        self.assertEqual(self.client.get("/admin").status_code, 403)
        # role se bere ze skupin při každém requestu; spc-admin = admin
        self.assertEqual(self.as_user("novak", "spc-users|spc-admin").status_code, 200)
        self.assertEqual(self.client.get("/admin").status_code, 200)
        with sqlite3.connect(self.app.config["DATABASE"]) as db:
            rows = db.execute("SELECT username, role, display_name, password_hash FROM users").fetchall()
        self.assertEqual(rows, [("novak", "admin", "Jan Novák", "!sso")])

    def test_existing_user_keeps_id_and_history(self):
        self.login("technik")
        self.client.post("/changes", data={"changed_at":"2026-09-11T09:00","machine_id":1,"tool_id":1,"description":"Před migrací.","result_status":"confirmed"})
        with sqlite3.connect(self.app.config["DATABASE"]) as db:
            db.execute("UPDATE users SET password_hash='pbkdf2:sha256:stare', role='technolog' WHERE username='technik'")
        self.as_user("technik", "spc-users|processlog-admin")
        self.assertIn("Před migrací".encode(), self.client.get("/history").data)
        with sqlite3.connect(self.app.config["DATABASE"]) as db:
            self.assertEqual(db.execute("SELECT id, role FROM users WHERE username='technik'").fetchone(), (1, "admin"))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)

    def test_logout_goes_to_authentik(self):
        self.login()
        response = self.client.post("/logout")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/outpost.goauthentik.io/sign_out"))
        self.assertEqual(self.client.get("/login").status_code, 404)
        self.assertEqual(self.client.get("/account/password").status_code, 404)
