# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class PunchoutBackend(models.Model):
    _inherit = "punchout.backend"

    cxml_order_send = fields.Boolean(
        string="Send orders as cXML",
        compute="_compute_cxml_order_send",
        store=True,
        help="Set when the backend's Order transmission is cXML OrderRequest: "
        "a confirmed purchase order for this supplier can then be transmitted "
        "back as a cXML OrderRequest. Not every cXML supplier accepts orders "
        "this way (some are catalog-only and take orders by email/EDI), so "
        "cXML is only offered where it is a supported channel.",
    )
    order_request_url = fields.Char(
        string="OrderRequest endpoint",
        help="URL the cXML OrderRequest is POSTed to. Often different from the "
        "PunchOutSetup URL — ask the supplier.",
    )
    order_email = fields.Char(
        string="Order email (fallback)",
        help="Supplier inbox for orders when no cXML transmission is used "
        "(informational).",
    )

    @api.depends("order_transmission_id.code")
    def _compute_cxml_order_send(self):
        """Derived from the Order transmission choice (single source of truth)."""
        for backend in self:
            backend.cxml_order_send = backend.order_transmission_id.code == "cxml"
