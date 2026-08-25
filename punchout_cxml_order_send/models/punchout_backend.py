# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class PunchoutBackend(models.Model):
    _inherit = "punchout.backend"

    cxml_order_send = fields.Boolean(
        string="Send orders as cXML",
        help="When enabled, a confirmed purchase order for this supplier can be "
        "transmitted back as a cXML OrderRequest. Not every cXML supplier "
        "accepts orders this way (some are catalog-only and take orders by "
        "email/EDI) — enable only for suppliers that do.",
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
