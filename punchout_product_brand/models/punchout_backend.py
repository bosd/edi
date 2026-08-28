# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PunchoutBackend(models.Model):
    _inherit = "punchout.backend"

    def _punchout_map_brand(self, product, value, overwrite=False):
        """Set the product brand from a cart value.

        The (already lookup-translated) value is matched to an existing
        ``product.brand`` by name, case-insensitively; if none exists it is
        created. This covers both value-translation styles: a supplier that
        returns a brand *name* maps directly, while a supplier that returns
        a brand *code* is translated to the name through the rule's lookup
        table first."""
        if product.product_brand_id and not overwrite:
            return
        name = str(value).strip()
        if not name:
            return
        Brand = self.env["product.brand"].sudo()
        brand = Brand.search([("name", "=ilike", name)], limit=1)
        if not brand:
            brand = Brand.create({"name": name})
            _logger.info(
                "[punchout.map] created product.brand %r for %s.",
                name,
                product.display_name,
            )
        product.sudo().product_brand_id = brand.id
