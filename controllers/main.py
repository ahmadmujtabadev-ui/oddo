"""REST routes. A controller only turns HTTP into Python and back; the rules live in services/.

Auth:    Authorization: Bearer <API key>   (Odoo: Preferences > Account Security > New API Key)
Company: add ?company_id=<id> to work in one company (default: all companies the user belongs to)
Reply:   {"data": ...} on success, {"error": "message"} with 400 / 401 / 403 / 404 on failure
"""
import functools

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

from ..services import invoice as invoice_service
from ..services import purchase as purchase_service
from ..services import sale as sale_service

GET = {"auth": "bearer", "methods": ["GET"]}
POST = {"auth": "bearer", "methods": ["POST"], "csrf": False}


def api(handler):
    """Company scope, one transaction (rolled back on error) and JSON errors for every route."""

    @functools.wraps(handler)
    def wrapper(*args, **kwargs):
        try:
            _use_company(kwargs.pop("company_id", None))
            with request.env.cr.savepoint():
                result = handler(*args, **kwargs)
        except AccessError as error:
            return _reply({"error": error.args[0]}, 403)
        except MissingError as error:
            return _reply({"error": error.args[0]}, 404)
        except UserError as error:  # also ValidationError
            return _reply({"error": error.args[0]}, 400)
        data, status = result if isinstance(result, tuple) else (result, 200)
        return _reply({"data": data}, status)

    return wrapper


def _reply(payload, status):
    return request.make_json_response(payload, status=status)


def _use_company(company_id):
    if company_id is None:
        return
    try:
        company_id = int(company_id)
    except ValueError:
        raise UserError(request.env._("'company_id' must be a whole number."))
    if company_id not in request.env.user.company_ids.ids:
        raise AccessError(request.env._("You do not belong to company %s.", company_id))
    request.update_context(allowed_company_ids=[company_id])


def _body():
    try:
        data = request.get_json_data()
    except ValueError:
        raise UserError(request.env._("The request body must be valid JSON."))
    if not isinstance(data, dict):
        raise UserError(request.env._("The request body must be a JSON object."))
    return data


def _int(data, key):
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise UserError(request.env._("'%s' must be a whole number.", key))
    return value


def _number(data, key):
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UserError(request.env._("'%s' must be a number.", key))
    return value


def _lines(data):
    lines = data.get("lines")
    if not isinstance(lines, list) or not lines or not all(isinstance(line, dict) for line in lines):
        raise UserError(request.env._("'lines' must be a non-empty list of objects."))
    return [
        {"product_id": _int(line, "product_id"), "quantity": _int(line, "quantity")}
        for line in lines
    ]


def _all(model, limit):
    try:
        limit = int(limit)
    except ValueError:
        raise UserError(request.env._("'limit' must be a whole number."))
    return request.env[model].search([], limit=limit)


def _get(model, record_id):
    # search() applies the company rules, so another company's record is simply "not found".
    record = request.env[model].search([("id", "=", record_id)])
    if not record:
        raise MissingError(request.env._("Record %s not found.", record_id))
    return record


def _product(product):
    return {
        "id": product.id,
        "name": product.name,
        "company": product.company_id.name,
        "price": product.price,
        "on_hand": product.quantity,
    }


def _move(move):
    return {
        "id": move.id,
        "date": move.date,
        "company": move.company_id.name,
        "product_id": move.product_id.id,
        "product": move.product_id.name,
        "quantity": move.quantity,
        "origin": move.origin,
    }


def _sale(order):
    return {
        "id": order.id,
        "number": order.name,
        "company": order.company_id.name,
        "customer": {"id": order.partner_id.id, "name": order.partner_id.name},
        "date": order.date,
        "state": order.state,
        "total": order.amount_total,
        "invoice_id": order.invoice_id.id or None,
        "lines": [
            {
                "product_id": line.product_id.id,
                "product": line.product_id.name,
                "quantity": line.quantity,
                "unit_price": line.price_unit,
                "subtotal": line.subtotal,
            }
            for line in order.line_ids
        ],
    }


def _purchase(order):
    return {
        "id": order.id,
        "number": order.name,
        "company": order.company_id.name,
        "vendor": {"id": order.partner_id.id, "name": order.partner_id.name},
        "date": order.date,
        "state": order.state,
        "lines": [
            {"product_id": line.product_id.id, "product": line.product_id.name, "quantity": line.quantity}
            for line in order.line_ids
        ],
    }


def _invoice(invoice):
    return {
        "id": invoice.id,
        "number": invoice.name,
        "company": invoice.company_id.name,
        "sale_id": invoice.sale_id.id,
        "customer": {"id": invoice.partner_id.id, "name": invoice.partner_id.name},
        "total": invoice.amount_total,
        "paid": invoice.amount_paid,
        "due": invoice.amount_due,
        "state": invoice.state,
    }


# ----------------------------------------------------------------- routes
class ErpApi(http.Controller):

    @http.route("/api/products", **GET)
    @api
    def list_products(self, limit=100, **kw):
        return [_product(p) for p in _all("erp.product", limit)]

    @http.route("/api/stock-moves", **GET)
    @api
    def list_stock_moves(self, limit=100, **kw):
        return [_move(m) for m in _all("erp.stock.move", limit)]

    # --- sales
    @http.route("/api/sales", **GET)
    @api
    def list_sales(self, limit=100, **kw):
        return [_sale(o) for o in _all("erp.sale.order", limit)]

    @http.route("/api/sales", **POST)
    @api
    def create_sale(self, **kw):
        body = _body()
        order = sale_service.create_order(request.env, _int(body, "customer_id"), _lines(body))
        return _sale(order), 201

    @http.route("/api/sales/<int:order_id>", **GET)
    @api
    def get_sale(self, order_id, **kw):
        return _sale(_get("erp.sale.order", order_id))

    @http.route("/api/sales/<int:order_id>/confirm", **POST)
    @api
    def confirm_sale(self, order_id, **kw):
        order = _get("erp.sale.order", order_id)
        sale_service.confirm(order)
        return _sale(order)

    # --- purchases
    @http.route("/api/purchases", **GET)
    @api
    def list_purchases(self, limit=100, **kw):
        return [_purchase(o) for o in _all("erp.purchase.order", limit)]

    @http.route("/api/purchases", **POST)
    @api
    def create_purchase(self, **kw):
        body = _body()
        order = purchase_service.create_order(request.env, _int(body, "vendor_id"), _lines(body))
        return _purchase(order), 201

    @http.route("/api/purchases/<int:order_id>/receive", **POST)
    @api
    def receive_purchase(self, order_id, **kw):
        order = _get("erp.purchase.order", order_id)
        purchase_service.receive(order)
        return _purchase(order)

    # --- invoices
    @http.route("/api/invoices", **GET)
    @api
    def list_invoices(self, limit=100, **kw):
        return [_invoice(i) for i in _all("erp.invoice", limit)]

    @http.route("/api/invoices/<int:invoice_id>", **GET)
    @api
    def get_invoice(self, invoice_id, **kw):
        return _invoice(_get("erp.invoice", invoice_id))

    @http.route("/api/invoices/<int:invoice_id>/payments", **POST)
    @api
    def pay_invoice(self, invoice_id, **kw):
        invoice = _get("erp.invoice", invoice_id)
        invoice_service.pay(invoice, _number(_body(), "amount"))
        return _invoice(invoice), 201
