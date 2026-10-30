"""Invoice rules."""


def pay(invoice, amount):
    """Logic 6: a payment lowers the amount due; the model marks the invoice paid at zero due."""
    invoice.env["erp.payment"].create({"invoice_id": invoice.id, "amount": amount})
    return invoice
