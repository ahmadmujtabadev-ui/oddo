import json

from odoo.tests.common import HttpCase, tagged

ROLES = ("sales", "purchase", "warehouse", "accountant")


@tagged("post_install", "-at_install")
class TestApi(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.ref("my_module.company_a")
        cls.company_b = cls.env.ref("my_module.company_b")
        cls.partner = cls.env["res.partner"].create({"name": "API Partner"})
        cls.laptop = cls.env["erp.product"].create(
            {"name": "API Laptop", "company_id": cls.company_a.id, "price": 1000}
        )
        cls.keys = {role: cls._api_key(role) for role in ROLES}

    @classmethod
    def _api_key(cls, role):
        user = cls.env["res.users"].create(
            {
                "name": f"API {role}",
                "login": f"api_{role}",
                "company_id": cls.company_a.id,
                "company_ids": [(6, 0, [cls.company_a.id])],
                "groups_id": [(6, 0, [cls.env.ref(f"my_module.group_erp_{role}").id])],
            }
        )
        return cls.env["res.users.apikeys"].with_user(user).sudo()._generate(None, "test", None)

    def _call(self, role, method, path, body=None):
        headers = {"Authorization": f"Bearer {self.keys[role]}", "Content-Type": "application/json"}
        if method == "POST":
            response = self.url_open(path, data=json.dumps(body or {}), headers=headers)
        else:
            response = self.url_open(path, headers=headers)
        return response.status_code, response.json()

    def _order_body(self, party_key, quantity):
        return {party_key: self.partner.id, "lines": [{"product_id": self.laptop.id, "quantity": quantity}]}

    def test_full_chain_over_http(self):
        a = f"company_id={self.company_a.id}"

        status, body = self._call("purchase", "POST", f"/api/purchases?{a}", self._order_body("vendor_id", 10))
        self.assertEqual(status, 201)
        purchase_id = body["data"]["id"]
        status, body = self._call("warehouse", "POST", f"/api/purchases/{purchase_id}/receive?{a}")
        self.assertEqual((status, body["data"]["state"]), (200, "received"))

        _, body = self._call("sales", "GET", f"/api/products?{a}")
        self.assertEqual({p["name"]: p["on_hand"] for p in body["data"]}["API Laptop"], 10)

        status, body = self._call("sales", "POST", f"/api/sales?{a}", self._order_body("customer_id", 4))
        self.assertEqual(status, 201)
        sale_id = body["data"]["id"]
        status, body = self._call("sales", "POST", f"/api/sales/{sale_id}/confirm?{a}")
        self.assertEqual((status, body["data"]["state"]), (200, "confirmed"))
        invoice_id = body["data"]["invoice_id"]
        self.assertTrue(invoice_id)

        status, body = self._call("accountant", "POST", f"/api/invoices/{invoice_id}/payments?{a}", {"amount": 1500})
        self.assertEqual((status, body["data"]["due"], body["data"]["state"]), (201, 2500, "unpaid"))
        status, body = self._call("accountant", "POST", f"/api/invoices/{invoice_id}/payments?{a}", {"amount": 2500})
        self.assertEqual((status, body["data"]["due"], body["data"]["state"]), (201, 0, "paid"))

    def test_errors_are_json_with_the_right_status(self):
        a = f"company_id={self.company_a.id}"

        status, body = self._call("sales", "POST", f"/api/sales?{a}", self._order_body("customer_id", 5))
        sale_id = body["data"]["id"]
        status, body = self._call("sales", "POST", f"/api/sales/{sale_id}/confirm?{a}")
        self.assertEqual(status, 400)
        self.assertIn("Not enough stock", body["error"])

        status, body = self._call("purchase", "POST", f"/api/purchases?{a}", self._order_body("vendor_id", 5))
        status, body = self._call("purchase", "POST", f"/api/purchases/{body['data']['id']}/receive?{a}")
        self.assertEqual(status, 403)

        status, body = self._call("sales", "POST", f"/api/sales?{a}", {"lines": []})
        self.assertEqual(status, 400)

        status, body = self._call("sales", "GET", f"/api/products?company_id={self.company_b.id}")
        self.assertEqual(status, 403)

        status, body = self._call("sales", "GET", "/api/sales/999999")
        self.assertEqual(status, 404)

        response = self.url_open("/api/products")
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())
        self.assertIn("Bearer", response.headers["WWW-Authenticate"])
