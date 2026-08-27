# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Punchout OCI Purchase",
    "version": "19.0.1.3.0",
    "license": "AGPL-3",
    "summary": "Create purchase orders from OCI shopping carts",
    "author": (
        "Hunki Enterprises BV, OBS Solutions Netherlands, "
        "Odoo Community Association (OCA)"
    ),
    "maintainers": ["hbrunn", "bosd"],
    "website": "https://github.com/OCA/edi",
    "depends": [
        "punchout_oci",
        "punchout_purchase",
    ],
    "auto_install": True,
}
