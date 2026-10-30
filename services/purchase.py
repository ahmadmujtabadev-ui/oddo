"""Purchase rules."""
from odoo.exceptions import AccessError, UserError

from . import stock


def create_order(env, partner_id, lines):
    """lines: [{"product_id": int, "quantity": int}, ...]"""
    return env["erp.purchase.order"].create(
        {
            "partner_id": partner_id,
            "line_ids": [(0, 0, line) for line in lines],
        }
    )


def receive(order):
    """Logic 4: adds stock once per order. Only the Warehouse role receives."""
    if not (order.env.su or order.env.user.has_group("my_module.group_erp_warehouse")):
        raise AccessError(order.env._("Only the Warehouse role can receive purchase orders."))
    if order.state != "draft":
        raise UserError(order.env._("%s has already been received.", order.name))
    if not order.line_ids:
        raise UserError(order.env._("Add at least one line before receiving."))
    stock.put_in(order.line_ids, origin=order.name)
    order.state = "received"
