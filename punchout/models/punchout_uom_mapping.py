# Copyright 2023 ACSONE SA/NV
# Copyright 2025 Bosd (migration to 18.0)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PunchoutUomMapping(models.Model):
    """Map supplier-specific UoM codes to Odoo UoMs.

    Suppliers may use non-standard UoM codes in their punchout catalogs.
    This model allows defining custom mappings per backend to convert
    supplier codes to the correct Odoo UoM.

    The mapping priority is:
    1. Backend-specific mapping (this model)
    2. UNECE code on uom.uom (from uom_unece module)
    3. UoM name exact match
    """

    _name = "punchout.uom.mapping"
    _description = "Punchout UoM Mapping"
    _sql_constraints = [
        (
            "backend_supplier_code_unique",
            "unique(backend_id, supplier_code)",
            "A mapping for this supplier code already exists for this backend.",
        ),
    ]

    backend_id = fields.Many2one(
        comodel_name="punchout.backend",
        required=True,
        ondelete="cascade",
        index=True,
    )
    supplier_code = fields.Char(
        required=True,
        help="The UoM code used by the supplier in punchout responses.",
    )
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UoM",
        required=True,
        ondelete="restrict",
        help="The Odoo UoM to use for products with this supplier code.",
    )
    notes = fields.Text(
        help="Optional notes about this mapping.",
    )

    @api.constrains("supplier_code")
    def _check_supplier_code(self):
        for rec in self:
            if not rec.supplier_code or not rec.supplier_code.strip():
                raise ValidationError(
                    _("Supplier code cannot be empty for mapping %(name)s")
                    % {"name": rec.display_name}
                )

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.supplier_code} -> {rec.uom_id.name}"
            result.append((rec.id, name))
        return result

    @api.model
    def _get_uom_by_supplier_code(self, backend, supplier_code):
        """Get Odoo UoM for a supplier code.

        Args:
            backend: punchout.backend record
            supplier_code: string code from supplier

        Returns:
            uom.uom record or False
        """
        if not supplier_code:
            return False

        supplier_code = supplier_code.strip()

        # 1. Check backend-specific mapping
        mapping = self.search(
            [
                ("backend_id", "=", backend.id),
                ("supplier_code", "=", supplier_code),
            ],
            limit=1,
        )
        if mapping:
            return mapping.uom_id

        # 2. Check UNECE code
        uom = self.env["uom.uom"].search(
            [("unece_code", "=", supplier_code)],
            limit=1,
        )
        if uom:
            return uom

        # 3. Check exact name match (case-insensitive)
        uom = self.env["uom.uom"].search(
            [("name", "=ilike", supplier_code)],
            limit=1,
        )
        if uom:
            return uom

        return False
