# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Punchout",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Odoo Community Association (OCA), ACSONE SA/NV",
    "website": "https://github.com/OCA/edi",
    "depends": [
        # odoo addons
        "base",
        "mail",
        # OCA addons
        "uom_unece",  # For UNECE UoM codes
    ],
    "data": [
        "security/punchout_backend.xml",
        "security/punchout_session.xml",
        "security/punchout_uom_mapping.xml",
        "data/cxml/common.xml",
        "data/cxml/punchout_setup_request.xml",
        "views/punchout_backend.xml",
        "views/punchout_session.xml",
        "views/punchout_uom_mapping.xml",
    ],
    "external_dependencies": {"python": ["lxml"]},
}
