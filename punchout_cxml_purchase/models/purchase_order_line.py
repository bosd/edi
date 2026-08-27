# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    punchout_supplier_aux_id = fields.Char(
        string="Punchout Supplier Aux. ID",
        copy=False,
        help=(
            "cXML SupplierPartAuxiliaryID captured from the punchout cart "
            "line. It identifies the specific cart item at the supplier and "
            "can carry per-line personalisation (e.g. a gift-card text). "
            "Suppliers that need it -- e.g. Topgeschenken -- require it "
            "echoed back unchanged in the cXML OrderRequest so they can "
            "match the order line to the original cart item."
        ),
    )
