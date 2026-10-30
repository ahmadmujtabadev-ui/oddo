from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Invoice(models.Model):
    _name = "erp.invoice"
    _description = "Invoice"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(string="Number", default="New", copy=False, readonly=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    sale_id = fields.Many2one(
        "erp.sale.order", string="Sale Order", required=True, ondelete="restrict",
        check_company=True,
    )
    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, check_company=True
    )
    amount_total = fields.Monetary(required=True)
    payment_ids = fields.One2many("erp.payment", "invoice_id", string="Payments")
    amount_paid = fields.Monetary(compute="_compute_amounts", store=True)
    amount_due = fields.Monetary(compute="_compute_amounts", store=True)
    state = fields.Selection(
        [("unpaid", "Unpaid"), ("paid", "Paid")], compute="_compute_amounts", store=True
    )

    _sql_constraints = [
        ("sale_uniq", "unique(sale_id)", "A sale order can only have one invoice."),
    ]

    @api.depends("amount_total", "payment_ids.amount")
    def _compute_amounts(self):
        """Logic 6: a payment reduces the amount due, and zero due means paid."""
        for invoice in self:
            invoice.amount_paid = sum(invoice.payment_ids.mapped("amount"))
            invoice.amount_due = invoice.amount_total - invoice.amount_paid
            invoice.state = "paid" if invoice.currency_id.is_zero(invoice.amount_due) else "unpaid"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("erp.invoice") or "New"
        return super().create(vals_list)


class Payment(models.Model):
    _name = "erp.payment"
    _description = "Payment"
    _order = "date desc, id desc"

    invoice_id = fields.Many2one(
        "erp.invoice", required=True, ondelete="cascade", readonly=True
    )
    company_id = fields.Many2one(related="invoice_id.company_id", store=True)
    currency_id = fields.Many2one(related="invoice_id.currency_id")
    date = fields.Date(default=fields.Date.context_today)
    amount = fields.Monetary(required=True)

    @api.constrains("amount", "invoice_id")
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_("The payment amount must be greater than zero."))
            invoice = payment.invoice_id
            if invoice.currency_id.compare_amounts(invoice.amount_due, 0) < 0:
                raise ValidationError(_("The payment is more than the amount due."))
