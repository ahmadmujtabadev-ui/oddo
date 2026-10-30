"""Sale rules."""
from odoo.exceptions import UserError

from . import stock


def create_order(env, partner_id, lines):
    """lines: [{"product_id": int, "quantity": int}, ...]"""
    return env["erp.sale.order"].create(
        {
            "partner_id": partner_id,
            "line_ids": [(0, 0, line) for line in lines],
        }
    )


def confirm(order):
    """Logic 2 and 5: blocked if stock is short, otherwise stock goes out and one invoice is made."""
    if order.state != "draft":
        raise UserError(order.env._("Only draft orders can be confirmed."))
    if not order.line_ids:
        raise UserError(order.env._("Add at least one line before confirming."))
    stock.check_available(order.line_ids)
    stock.take_out(order.line_ids, origin=order.name)
    order.invoice_id = _create_invoice(order)
    order.state = "confirmed"


def _create_invoice(order):
    return order.env["erp.invoice"].sudo().create(
        {
            "sale_id": order.id,
            "company_id": order.company_id.id,
            "partner_id": order.partner_id.id,
            "amount_total": order.amount_total,
        }
    )
