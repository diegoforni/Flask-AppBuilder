import json
import unittest
from uuid import uuid4


def _post_json(client, url, payload, headers=None):
    return client.post(url, data=json.dumps(payload), headers={"Content-Type": "application/json", **(headers or {})})


class InitialRoutinesTest(unittest.TestCase):
    def test_register_seeds_default_routines(self):
        from app import app

        client = app.test_client()

        unique = str(uuid4())[:8]
        email = f"seed_{unique}@example.com"
        password = "Passw0rd!"

        r = _post_json(client, "/api/register", {"email": email, "password": password})
        self.assertIn(r.status_code, (200, 201), r.data)

        # login to get token
        r2 = _post_json(client, "/api/login", {"email": email, "password": password})
        self.assertEqual(r2.status_code, 200, r2.data)
        token = r2.get_json()["token"]

        # list routines and ensure at least the two defaults exist
        lr = client.get("/api/routines", headers={"Authorization": token})
        self.assertEqual(lr.status_code, 200, lr.data)
        data = lr.get_json()
        names = {x.get("name") for x in data}
        self.assertIn("Magia de Cerca con Cartas", names)
        self.assertIn("Camareando", names)


if __name__ == "__main__":
    unittest.main()

