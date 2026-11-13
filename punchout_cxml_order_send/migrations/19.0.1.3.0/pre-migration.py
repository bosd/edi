# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""``cxml_order_send`` becomes computed from ``order_transmission_id``.

Before the ORM recomputes it, move every backend that had the old checkbox
ticked onto the cXML OrderRequest channel (and list cXML as a supported
channel), so no backend silently stops sending orders.
"""

from odoo.tools import sql


def migrate(cr, version):
    if not version:
        return
    if not sql.column_exists(cr, "punchout_backend", "cxml_order_send"):
        return
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
         WHERE module = 'punchout_cxml_order_send'
           AND name = 'transmission_cxml'
           AND model = 'punchout.order.transmission'
        """
    )
    row = cr.fetchone()
    if not row:
        return
    cxml_id = row[0]
    cr.execute(
        """
        INSERT INTO punchout_backend_supported_transmission_rel
               (backend_id, transmission_id)
        SELECT id, %s FROM punchout_backend WHERE cxml_order_send
        ON CONFLICT DO NOTHING
        """,
        (cxml_id,),
    )
    cr.execute(
        """
        UPDATE punchout_backend SET order_transmission_id = %s
         WHERE cxml_order_send
           AND order_transmission_id IS DISTINCT FROM %s
        """,
        (cxml_id, cxml_id),
    )
