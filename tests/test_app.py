import os
import sqlite3
import tempfile
import unittest

from app import create_app


class ProcessLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE": os.path.join(self.tmp.name, "test.db"), "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def login(self, username="admin", password="admin123"):
        return self.client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

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

    def test_user_can_change_password(self):
        self.login()
        response = self.client.post("/account/password", data={"current_password": "admin123", "new_password": "noveheslo1", "confirmation": "noveheslo1"}, follow_redirects=True)
        self.assertIn("Heslo bylo změněno".encode(), response.data)

    def test_admin_can_reset_user_and_deactivate_tool(self):
        self.login()
        response = self.client.post("/admin/users/2", data={"display_name": "Jan Svoboda", "role": "technolog", "active": "on", "password": "reset123"}, follow_redirects=True)
        self.assertIn("Heslo bylo resetováno".encode(), response.data)
        self.client.post("/logout")
        self.assertIn("Nová procesní změna".encode(), self.login("technik", "reset123").data)
        self.client.post("/logout")
        self.login()
        self.client.post("/admin/tools/1/active", data={"action": "deactivate"})
        self.assertEqual(self.client.get("/api/catalog/tools?q=MO2945").get_json(), [])

    def test_history_is_shared_but_only_admin_can_delete(self):
        self.login()
        self.client.post("/changes", data={"changed_at":"2026-09-11T09:00","machine_id":1,"tool_id":1,"description":"Adminův společný záznam.","result_status":"confirmed"})
        self.client.post("/logout")
        self.login("technik", "technik123")
        self.assertIn("Adminův společný záznam".encode(), self.client.get("/history").data)
        self.assertEqual(self.client.post("/history/1/delete").status_code, 403)
        self.client.post("/logout")
        self.login()
        response = self.client.post("/history/1/delete", follow_redirects=True)
        self.assertIn("Záznam v historii byl smazán".encode(), response.data)


if __name__ == "__main__":
    unittest.main()
