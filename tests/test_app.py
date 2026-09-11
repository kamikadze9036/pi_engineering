import os
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

    def test_save_and_multisearch(self):
        self.login("technik", "technik123")
        machine = self.client.get("/api/catalog/machines?q=1100").get_json()[0]
        tool = self.client.get("/api/catalog/tools?q=MO2945").get_json()[0]
        response = self.client.post("/changes", data={"changed_at":"2026-09-11T09:00","machine_id":machine["id"],"tool_id":tool["id"],"description":"Dotlak upraven kvůli propadu.","result_status":"pending","parameter_name":"Dotlak","old_value":"420 bar","new_value":"455 bar"}, follow_redirects=True)
        self.assertIn("Procesní změna byla uložena".encode(), response.data)
        history = self.client.get("/history?q=propadu")
        self.assertIn("Dotlak upraven".encode(), history.data)


if __name__ == "__main__":
    unittest.main()
