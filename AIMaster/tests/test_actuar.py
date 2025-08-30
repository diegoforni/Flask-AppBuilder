import json
import unittest
from uuid import uuid4


def _post_json(client, url, payload, headers=None):
    return client.post(url, data=json.dumps(payload), headers={"Content-Type": "application/json", **(headers or {})})


class ActuarFlowTest(unittest.TestCase):
    def test_actuar_flow(self):
        # Import app only inside test to ensure environment is ready
        from app import app

        client = app.test_client()

        # Use a unique email per run to avoid collisions
        unique = str(uuid4())[:8]
        email = f"act_{unique}@example.com"
        password = "Passw0rd!"

        # Register user (may fail if exists, but unique avoids it)
        r = _post_json(client, "/api/register", {"email": email, "password": password})
        self.assertIn(r.status_code, (200, 201, 400))  # 400 when already exists

        # Login
        r = _post_json(client, "/api/login", {"email": email, "password": password})
        self.assertEqual(r.status_code, 200, r.data)
        token = r.get_json()["token"]

        # Post actuar text
        text1 = f"Hello world {unique}"
        r = _post_json(client, "/api/actuar", {"text": text1}, headers={"Authorization": token})
        self.assertEqual(r.status_code, 200, r.data)
        data = r.get_json()
        self.assertTrue(data.get("success"))
        static = data.get("static") or {}
        url = static.get("url")
        self.assertTrue(url and url.startswith("/static/actuar/"))

        # Static file should be readable via Flask static route
        sr = client.get(url)
        self.assertEqual(sr.status_code, 200)
        self.assertIn(text1, sr.get_data(as_text=True))

        # Public API by username
        pr = client.get(f"/api/actuar/{email}")
        self.assertEqual(pr.status_code, 200)
        pdata = pr.get_json()
        self.assertEqual(pdata["username"], email)
        self.assertEqual(pdata["text"], text1)

        # Update actuar text
        text2 = f"Updated {unique}"
        r2 = _post_json(client, "/api/actuar", {"text": text2}, headers={"Authorization": token})
        self.assertEqual(r2.status_code, 200)
        sr2 = client.get(url)
        self.assertEqual(sr2.status_code, 200)
        body2 = sr2.get_data(as_text=True)
        self.assertIn(text2, body2)
        self.assertNotIn(text1, body2)


if __name__ == "__main__":
    unittest.main()
