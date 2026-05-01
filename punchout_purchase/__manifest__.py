# Copyright 2023 ACSONE SA/NV
# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Punchout Purchase",
    "version": "19.0.1.3.1",
    "license": "AGPL-3",
    "summary": "Create purchase orders from Punchout shopping carts",
    "author": (
        "ACSONE SA/NV, Hunki Enterprises BV, OBS Solutions Netherlands, "
        "Odoo Community Association (OCA)"
    ),
    "maintainers": ["bosd"],
    "website": "https://github.com/OCA/edi",
    "depends": [
        "punchout",
        "purchase",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/punchout_backend.xml",
        "views/punchout_session.xml",
        "views/purchase_order.xml",
        "views/res_partner.xml",
        "views/product_template.xml",
        "views/product_supplierinfo.xml",
    ],
    "demo": [
        "demo/punchout_purchase_demo.xml",
    ],
}
