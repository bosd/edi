# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PunchoutFieldMapping(models.Model):
    """Per-backend rule mapping one supplier cart field to one Odoo target.

    Punchout carts are supplier-specific: the same logical datum (a
    barcode, a brand, an image URL) lands in a different cart field for
    every vendor — e.g. Van Egmond returns the GTIN in ``CUST_FIELD1``
    while another OCI vendor uses ``VENDORMAT``. Rather than hardcode one
    field name per concern, each backend carries a list of these rules,
    shipped in its preset and editable by a Punchout Manager.

    The engine (``punchout.backend._apply_product_field_mappings``) is
    protocol-agnostic: each protocol module flattens one cart line to a
    ``{source_field: value}`` dict, and the rules do the rest. The set of
    ``target`` values is extensible — targets that need an optional OCA
    module (e.g. ``brand`` → ``product_brand``) are contributed by small
    bridge modules that override ``_selection_target`` and add the
    matching ``_punchout_map_<target>`` handler, so this base module
    depends on nothing optional.
    """

    _name = "punchout.field.mapping"
    _description = "Punchout Cart-Field Mapping"
    _order = "backend_id, sequence, id"

    backend_id = fields.Many2one(
        comodel_name="punchout.backend",
        string="Backend",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    source_field = fields.Char(
        required=True,
        help=(
            "Name of the field as it arrives in the supplier's cart line. "
            "For OCI this is the ``NEW_ITEM-<name>`` key without the prefix "
            "and index (e.g. ``CUST_FIELD1``, ``ATTACHMENT``, ``VENDORMAT``, "
            "``MATGROUP``). For cXML it is a flattened key such as "
            "``SupplierPartID``, ``ManufacturerPartID``, ``Description`` or "
            "``Classification:<domain>``."
        ),
    )
    target = fields.Selection(
        selection="_selection_target",
        required=True,
        help="Which Odoo field on the (auto-created) product this rule feeds.",
    )
    value_transform = fields.Selection(
        selection=[
            ("direct", "Direct"),
            ("lookup_table", "Lookup table"),
        ],
        default="direct",
        required=True,
        help=(
            "Direct: the raw cart value is used as-is. Lookup table: the raw "
            "value is translated through the rows below (e.g. a supplier "
            "brand code → an Odoo brand name); an unmapped raw value is "
            "skipped."
        ),
    )
    value_mapping_ids = fields.One2many(
        comodel_name="punchout.value.mapping",
        inverse_name="mapping_id",
        string="Value lookup",
    )
    overwrite = fields.Boolean(
        default=False,
        help=(
            "When off (default), the rule only fills the target when it is "
            "still empty on the product — so manual corrections and values "
            "from an earlier punchout survive a re-punchout. Turn it on to "
            "always overwrite with the latest supplier value."
        ),
    )

    def _selection_target(self):
        """Return the list of ``(key, label)`` targets a rule can write.

        Kept minimal and always-safe in this base module. Bridge modules
        for optional OCA add-ons append their own (see
        ``punchout_product_brand``)."""
        return [
            ("barcode", "Barcode (GTIN/EAN)"),
            ("image", "Product image (from URL)"),
            ("description", "Purchase description"),
            ("product_code", "Supplier product code"),
            ("unspsc_category", "UNSPSC category (deferred)"),
        ]

    def _resolve_value(self, raw):
        """Translate a raw cart value per ``value_transform``.

        Returns the resolved string, or ``None`` when there is nothing to
        write (empty, or an unmapped lookup value)."""
        self.ensure_one()
        text = ("" if raw is None else str(raw)).strip()
        if not text:
            return None
        if self.value_transform == "lookup_table":
            match = self.value_mapping_ids.filtered(
                lambda line: (line.raw or "").strip().lower() == text.lower()
            )
            resolved = (match[:1].value or "").strip()
            return resolved or None
        return text


class PunchoutValueMapping(models.Model):
    """One ``raw → value`` row of a mapping rule's lookup table."""

    _name = "punchout.value.mapping"
    _description = "Punchout Value Lookup Row"
    _order = "mapping_id, raw"

    mapping_id = fields.Many2one(
        comodel_name="punchout.field.mapping",
        string="Mapping",
        required=True,
        ondelete="cascade",
        index=True,
    )
    raw = fields.Char(
        required=True,
        help="Raw value as it arrives in the supplier cart.",
    )
    value = fields.Char(
        required=True,
        help="Value written into Odoo (e.g. a brand name or category code).",
    )
