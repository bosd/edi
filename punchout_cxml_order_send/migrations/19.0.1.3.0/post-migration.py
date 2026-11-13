# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Fabory takes orders as e-PDF only; earlier versions listed cXML
OrderRequest as a supported channel on its preset. Remove it again unless
someone deliberately chose cXML as Fabory's order transmission.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {"active_test": False})
    fabory = env.ref("punchout_cxml.preset_fabory", raise_if_not_found=False)
    cxml = env.ref(
        "punchout_cxml_order_send.transmission_cxml", raise_if_not_found=False
    )
    if not fabory or not cxml or fabory.order_transmission_id == cxml:
        return
    fabory.supported_transmission_ids = [(3, cxml.id)]
