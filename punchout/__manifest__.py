# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Punchout",
    "version": "19.0.1.4.0",
    "license": "AGPL-3",
    "author": (
        "ACSONE SA/NV, OBS Solutions Netherlands, Odoo Community Association (OCA)"
    ),
    "maintainers": ["bosd"],
    "website": "https://github.com/OCA/edi",
    "depends": [
        # odoo addons
        "base",
        "mail",
        # OCA addons
        "uom_unece",  # For UNECE UoM codes
    ],
    "data": [
        # Security groups must load before model-access entries
        # that reference them.
        "security/punchout_security.xml",
        "security/punchout_backend.xml",
        "security/punchout_session.xml",
        "security/punchout_uom_mapping.xml",
        "data/uom_mapping_data.xml",
        "data/ir_cron.xml",
        "views/punchout_backend.xml",
        "views/punchout_session.xml",
        "views/punchout_uom_mapping.xml",
    ],
    "demo": [
        "demo/punchout_demo.xml",
    ],
}
