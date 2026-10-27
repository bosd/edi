# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "PunchOut REST Order Send",
    "version": "19.0.1.0.0",
    "summary": "REST API order-transmission channel for PunchOut backends",
    "author": "Bosd, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/edi",
    "license": "AGPL-3",
    "category": "Purchases",
    "depends": [
        "punchout_purchase",
    ],
    "data": [
        "data/punchout_order_transmission_data.xml",
    ],
    "installable": True,
}
