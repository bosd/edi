# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Migrate ``order_transmission`` (Selection char) to the new
``order_transmission_id`` Many2one + seed ``supported_transmission_ids``.

Base handles the universal channels (manual, email) and seeds every
existing backend with {manual, email}. The now-dropped 'portal' maps to
'manual'. The channel modules (``punchout_cxml_order_send``,
``punchout_rest_order_send``) map their own codes and add their channel to
the presets that support it in their own post-migrations — the orphan
``order_transmission`` column survives the whole upgrade so they can read
it.
"""

from odoo import SUPERUSER_ID, api
from odoo.tools import sql


def migrate(cr, version):
    if not version:
        return
    # Nothing to do if the legacy column is already gone.
    if not sql.column_exists(cr, "punchout_backend", "order_transmission"):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    manual = env.ref("punchout.transmission_manual", raise_if_not_found=False)
    email = env.ref("punchout.transmission_email", raise_if_not_found=False)
    if not manual or not email:
        return

    backends = env["punchout.backend"].with_context(active_test=False).search([])
    # Seed the universal supported set on every existing backend (these
    # rows predate the field, so the Python default never ran for them).
    # One write for the whole set.
    universal = manual | email
    backends.supported_transmission_ids = [(4, rec.id) for rec in universal]

    # Map the legacy value for the base-owned codes only, grouping backends
    # by target channel so it is one write per channel rather than per row.
    code_to_rec = {"manual": manual, "email": email, "portal": manual}
    cr.execute(
        "SELECT id, order_transmission FROM punchout_backend "
        "WHERE order_transmission IS NOT NULL"
    )
    ids_by_rec = {}
    for backend_id, code in cr.fetchall():
        rec = code_to_rec.get(code)
        if rec:
            ids_by_rec.setdefault(rec.id, []).append(backend_id)
    for rec_id, backend_ids in ids_by_rec.items():
        env["punchout.backend"].browse(backend_ids).order_transmission_id = rec_id
