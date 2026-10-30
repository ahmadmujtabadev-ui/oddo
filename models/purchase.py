from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..services import purchase as purchase_service


class PurchaseOrder(models.Model):
    _name = "erp.purchase.order"
    _description = "Purchase Order"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(string="Number", default="New", copy=False, readonly=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    partner_id = fields.Many2one(
        "res.partner", string="Vendor", required=True, check_company=True
    )
    date = fields.Date(default=fields.Date.context_today)
    state = fields.Selection(
        [("draft", "Draft"), ("received", "Received")],
        default="draft",
        required=True,
        readonly=True,
        copy=False,
    )
    line_ids = fields.One2many("erp.purchase.order.line", "order_id", string="Lines")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("erp.purchase.order") or "New"
        return super().create(vals_list)

    def action_receive(self):
        for order in self:
            purchase_service.receive(order)


class PurchaseOrderLine(models.Model):
    _name = "erp.purchase.order.line"
    _description = "Purchase Order Line"
    _check_company_auto = True

    order_id = fields.Many2one("erp.purchase.order", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="order_id.company_id", store=True)
    product_id = fields.Many2one("erp.product", required=True, check_company=True)
    quantity = fields.Integer(default=1)

    @api.constrains("quantity")
    def _check_quantity(self):
        if any(line.quantity <= 0 for line in self):
            raise ValidationError(_("Quantity must be greater than zero."))
