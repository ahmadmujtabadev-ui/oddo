from werkzeug.exceptions import HTTPException

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _handle_error(cls, exception):
        """Errors raised before our code runs (missing or wrong API key, unknown URL) also use {"error": ...}."""
        if isinstance(exception, HTTPException) and request.httprequest.path.startswith("/api/"):
            headers = [h for h in exception.get_headers() if h[0] == "WWW-Authenticate"]
            return request.make_json_response(
                {"error": exception.description}, headers=headers, status=exception.code
            )
        return super()._handle_error(exception)
