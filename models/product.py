from odoo import _, api, fields, models
from odoo.exceptions import UserError


class Product(models.Model):
    _name = "erp.product"
    _description = "Product"

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    price = fields.Monetary(string="Sale Price")
    move_ids = fields.One2many("erp.stock.move", "product_id", string="Stock Moves")
    # Logic 3: never typed in, always the sum of the stock moves.
    quantity = fields.Integer(string="On Hand", compute="_compute_quantity", store=True)

    @api.depends("move_ids.quantity")
    def _compute_quantity(self):
        for product in self:
            product.quantity = sum(product.move_ids.mapped("quantity"))

    def unlink(self):
        for product in self:
            used = any(
                self.env[model].sudo().search_count([("product_id", "=", product.id)])
                for model in ("erp.sale.order.line", "erp.purchase.order.line", "erp.stock.move")
            )
            if used:
                raise UserError(
                    _("%s is used in an order or has stock moves, so it cannot be deleted.", product.name)
                )
        return super().unlink()


class StockMove(models.Model):
    """One line of the stock ledger. Created only by sales and purchases."""

    _name = "erp.stock.move"
    _description = "Stock Move"
    _order = "id desc"

    product_id = fields.Many2one(
        "erp.product", required=True, ondelete="restrict", readonly=True
    )
    company_id = fields.Many2one(related="product_id.company_id", store=True)
    quantity = fields.Integer(
        required=True, readonly=True, help="Positive = stock in, negative = stock out."
    )
    origin = fields.Char(string="Source", readonly=True)
    date = fields.Datetime(default=fields.Datetime.now, readonly=True)
