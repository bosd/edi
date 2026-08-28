# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class PunchoutFieldMapping(models.Model):
    _inherit = "punchout.field.mapping"

    def _selection_target(self):
        """Add the ``brand`` target (writes ``product.template.product_brand_id``).

        Contributed here rather than in ``punchout_purchase`` so the core
        module keeps no dependency on the optional ``product_brand``
        add-on."""
        return super()._selection_target() + [("brand", "Brand")]
