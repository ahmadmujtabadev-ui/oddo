"""Stock ledger rules. These functions are the only way stock moves are written."""
from collections import defaultdict

from odoo.exceptions import UserError


def check_available(lines):
    """Every product on the lines must have enough stock on hand."""
    wanted = defaultdict(int)
    for line in lines:
        wanted[line.product_id] += line.quantity
    for product, quantity in wanted.items():
        if product.quantity < quantity:
            raise UserError(
                lines.env._(
                    "Not enough stock for %(product)s: need %(need)s, have %(have)s. "
                    "Stock comes in by receiving a Purchase Order.",
                    product=product.name,
                    need=quantity,
                    have=product.quantity,
                )
            )


def take_out(lines, origin):
    _write_moves(lines, origin, -1)


def put_in(lines, origin):
    _write_moves(lines, origin, 1)


def _write_moves(lines, origin, sign):
    # No role has create access on the ledger, so this is the only door (sudo).
    lines.env["erp.stock.move"].sudo().create(
        [
            {
                "product_id": line.product_id.id,
                "quantity": sign * line.quantity,
                "origin": origin,
            }
            for line in lines
        ]
    )
