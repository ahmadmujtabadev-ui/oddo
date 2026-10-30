from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMyRecord(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.record = cls.env["my_module.record"].create(
            {"title": "Test", "amount": 100.0, "tax_rate": 10.0}
        )

    def test_sequence_and_total(self):
        self.assertTrue(self.record.name.startswith("REC/"))
        self.assertAlmostEqual(self.record.total, 110.0)

    def test_workflow(self):
        self.record.action_confirm()
        self.assertEqual(self.record.state, "confirmed")
        self.record.action_done()
        self.assertEqual(self.record.state, "done")

    def test_done_requires_confirm(self):
        with self.assertRaises(UserError):
            self.record.action_done()

    def test_negative_amount(self):
        with self.assertRaises(ValidationError):
            self.record.amount = -1
