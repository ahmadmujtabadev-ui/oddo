from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import sale as sale_service


class SaleOrder(models.Model):
    _name = "erp.sale.order"
    _description = "Sale Order"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(string="Number", default="New", copy=False, readonly=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, check_company=True
    )
    date = fields.Date(default=fields.Date.context_today)
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed")],
        default="draft",
        required=True,
        readonly=True,
        copy=False,
    )
    line_ids = fields.One2many("erp.sale.order.line", "order_id", string="Lines")
    amount_total = fields.Monetary(compute="_compute_amount_total", store=True)
    invoice_id = fields.Many2one("erp.invoice", readonly=True, copy=False)

    @api.depends("line_ids.subtotal")
    def _compute_amount_total(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped("subtotal"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("erp.sale.order") or "New"
        return super().create(vals_list)

    def action_confirm(self):
        for order in self:
            sale_service.confirm(order)

    def unlink(self):
        if any(order.state == "confirmed" for order in self):
            raise UserError(
                _("Confirmed sale orders cannot be deleted: they took stock out and have an invoice.")
            )
        return super().unlink()


class SaleOrderLine(models.Model):
    _name = "erp.sale.order.line"
    _description = "Sale Order Line"
    _check_company_auto = True

    order_id = fields.Many2one("erp.sale.order", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="order_id.company_id", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id")
    product_id = fields.Many2one("erp.product", required=True, check_company=True)
    quantity = fields.Integer(default=1)
    price_unit = fields.Monetary(
        string="Unit Price", compute="_compute_price_unit", store=True, readonly=False
    )
    subtotal = fields.Monetary(compute="_compute_subtotal", store=True)

    @api.depends("product_id")
    def _compute_price_unit(self):
        for line in self:
            line.price_unit = line.product_id.price

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.constrains("quantity")
    def _check_quantity(self):
        if any(line.quantity <= 0 for line in self):
            raise ValidationError(_("Quantity must be greater than zero."))
