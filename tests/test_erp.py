from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestErp(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.ref("my_module.company_a")
        cls.company_b = cls.env.ref("my_module.company_b")
        cls.partner = cls.env["res.partner"].create({"name": "Some Partner"})
        cls.laptop = cls.env["erp.product"].create(
            {"name": "Test Laptop", "company_id": cls.company_a.id, "price": 1000}
        )

    def _purchase(self, qty):
        order = self.env["erp.purchase.order"].create(
            {
                "company_id": self.company_a.id,
                "partner_id": self.partner.id,
                "line_ids": [(0, 0, {"product_id": self.laptop.id, "quantity": qty})],
            }
        )
        order.action_receive()
        return order

    def _sale(self, qty):
        return self.env["erp.sale.order"].create(
            {
                "company_id": self.company_a.id,
                "partner_id": self.partner.id,
                "line_ids": [(0, 0, {"product_id": self.laptop.id, "quantity": qty})],
            }
        )

    # 1. Company isolation
    def test_company_isolation(self):
        user_a = self.env["res.users"].create(
            {
                "name": "Sales A",
                "login": "sales_a",
                "company_id": self.company_a.id,
                "company_ids": [(6, 0, [self.company_a.id])],
                "groups_id": [(6, 0, [self.env.ref("my_module.group_erp_sales").id])],
            }
        )
        desk_b = self.env.ref("my_module.product_desk")
        products = self.env["erp.product"].with_user(user_a).search([])
        self.assertIn(self.laptop, products)
        self.assertNotIn(desk_b, products)
        with self.assertRaises(AccessError):
            desk_b.with_user(user_a).read(["name"])

    # 2. Sales confirm: blocked if stock is short, otherwise stock goes out
    def test_sale_blocked_when_stock_short(self):
        self._purchase(2)
        order = self._sale(5)
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(order.state, "draft")
        self.assertEqual(self.laptop.quantity, 2)

    def test_sale_takes_stock_out(self):
        self._purchase(10)
        self._sale(3).action_confirm()
        self.assertEqual(self.laptop.quantity, 7)

    # 3. Stock ledger: quantity is the sum of stock moves
    def test_quantity_is_sum_of_moves(self):
        self._purchase(10)
        self._sale(4).action_confirm()
        self.assertEqual(sorted(self.laptop.move_ids.mapped("quantity")), [-4, 10])
        self.assertEqual(self.laptop.quantity, sum(self.laptop.move_ids.mapped("quantity")))

    # 4. Purchase receive: adds stock once per order
    def test_purchase_receives_once(self):
        order = self._purchase(10)
        self.assertEqual(self.laptop.quantity, 10)
        with self.assertRaises(UserError):
            order.action_receive()
        self.assertEqual(self.laptop.quantity, 10)

    def test_only_warehouse_receives(self):
        purchase_user = self.env["res.users"].create(
            {
                "name": "Purchase A",
                "login": "purchase_a",
                "company_id": self.company_a.id,
                "company_ids": [(6, 0, [self.company_a.id])],
                "groups_id": [(6, 0, [self.env.ref("my_module.group_erp_purchase").id])],
            }
        )
        order = self.env["erp.purchase.order"].create(
            {
                "company_id": self.company_a.id,
                "partner_id": self.partner.id,
                "line_ids": [(0, 0, {"product_id": self.laptop.id, "quantity": 5})],
            }
        )
        with self.assertRaises(AccessError):
            order.with_user(purchase_user).action_receive()
        self.assertEqual(self.laptop.quantity, 0)

    def test_used_records_give_a_clear_error_on_delete(self):
        self._purchase(5)
        with self.assertRaises(UserError):
            self.laptop.unlink()
        unused = self.env["erp.product"].create({"name": "Unused", "company_id": self.company_a.id})
        unused.unlink()
        order = self._sale(1)
        order.action_confirm()
        with self.assertRaises(UserError):
            order.unlink()
        self._sale(1).unlink()

    # 5. Invoice: a confirmed sale creates one invoice
    def test_confirmed_sale_creates_one_invoice(self):
        self._purchase(10)
        order = self._sale(2)
        self.assertFalse(order.invoice_id)
        order.action_confirm()
        self.assertEqual(order.invoice_id.amount_total, 2000)
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(self.env["erp.invoice"].search_count([("sale_id", "=", order.id)]), 1)

    # 6. Payment: reduces the amount due, and zero due means paid
    def test_payment_reduces_due_and_zero_means_paid(self):
        self._purchase(10)
        order = self._sale(1)
        order.action_confirm()
        invoice = order.invoice_id
        self.assertEqual((invoice.amount_due, invoice.state), (1000, "unpaid"))

        self.env["erp.payment"].create({"invoice_id": invoice.id, "amount": 400})
        self.assertEqual((invoice.amount_due, invoice.state), (600, "unpaid"))

        self.env["erp.payment"].create({"invoice_id": invoice.id, "amount": 600})
        self.assertEqual((invoice.amount_due, invoice.state), (0, "paid"))

    def test_payment_cannot_exceed_amount_due(self):
        self._purchase(10)
        order = self._sale(1)
        order.action_confirm()
        with self.assertRaises(ValidationError):
            self.env["erp.payment"].create({"invoice_id": order.invoice_id.id, "amount": 1001})
