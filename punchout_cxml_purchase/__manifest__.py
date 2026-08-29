# Copyright 2023 ACSONE SA/NV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Punchout cXML Purchase",
    "version": "19.0.1.7.0",
    "license": "AGPL-3",
    "summary": "Create purchase orders from cXML shopping carts",
    "author": (
        "ACSONE SA/NV, OBS Solutions Netherlands, Odoo Community Association (OCA)"
    ),
    "maintainers": ["bosd"],
    "website": "https://github.com/OCA/edi",
    "depends": [
        "punchout_cxml",
        "punchout_purchase",
    ],
    "auto_install": True,
}
