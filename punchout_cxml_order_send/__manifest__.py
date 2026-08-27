# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "PunchOut cXML Order Send",
    "version": "19.0.1.1.0",
    "summary": "Send a confirmed purchase order to the supplier as a cXML OrderRequest",
    "author": "Bosd, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/edi",
    "license": "AGPL-3",
    "category": "Purchases",
    "depends": [
        "punchout_cxml_purchase",
    ],
    "data": [
        "data/cxml_order_request.xml",
        "views/punchout_backend_views.xml",
        "views/purchase_order_views.xml",
    ],
    "installable": True,
}
