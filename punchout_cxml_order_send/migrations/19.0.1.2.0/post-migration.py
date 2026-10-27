# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Map the legacy ``order_transmission = 'cxml'`` value to the new
``order_transmission_id`` Many2one and make sure those backends list cXML
in their supported set. Base already seeded {manual, email}; the module's
data file adds cXML to the shipped cXML presets — this covers any other
backend a user had set to cXML by hand.
"""

from odoo import SUPERUSER_ID, api
from odoo.tools import sql


def migrate(cr, version):
    if not version:
        return
    if not sql.column_exists(cr, "punchout_backend", "order_transmission"):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cxml = env.ref(
        "punchout_cxml_order_send.transmission_cxml", raise_if_not_found=False
    )
    if not cxml:
        return
    cr.execute("SELECT id FROM punchout_backend WHERE order_transmission = 'cxml'")
    ids = [row[0] for row in cr.fetchall()]
    for backend in env["punchout.backend"].browse(ids):
        backend.supported_transmission_ids = [(4, cxml.id)]
        backend.order_transmission_id = cxml.id
