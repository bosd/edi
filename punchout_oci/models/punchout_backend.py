# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class PunchoutBackend(models.Model):
    _inherit = "punchout.backend"

    # OCI-specific fields
    oci_version = fields.Selection(
        [("3.0", "3.0"), ("4.0", "4.0"), ("5.0", "5.0")],
        default="5.0",
        string="OCI Version",
    )
    oci_custom_parameters = fields.Char(
        string="Vendor-specific parameters",
        groups="base.group_system",
        help="Authentication parameters in query string format: "
        "username=user&password=pass. Escape hatch for params not "
        "covered by the generic auth_username / auth_password / "
        "auth_customer_number fields. Values here override the "
        "generic-auth splice when keys collide.",
    )

    # Per-supplier param-name mapping. Most OCI suppliers use the
    # uppercase ``USERNAME`` / ``PASSWORD`` / ``CUSTOMER`` defaults
    # (INDI, Würth, etc.); a few use lowercase or supplier-specific
    # names (TVH uses ``username`` / ``password``). Each preset
    # overrides as needed; managers don't see these — they live in
    # the Advanced section, gated to ``base.group_system``.
    oci_param_username = fields.Char(
        string="Username param name",
        default="USERNAME",
        groups="base.group_system",
        help="Form-POST parameter name the supplier expects for the "
        "username. Defaults to the OCI-conventional ``USERNAME``; "
        "override per supplier (e.g. TVH expects ``username`` "
        "lowercase).",
    )
    oci_param_password = fields.Char(
        string="Password param name",
        default="PASSWORD",
        groups="base.group_system",
        help="Form-POST parameter name for the password. Defaults to ``PASSWORD``.",
    )
    oci_param_customer = fields.Char(
        string="Customer-number param name",
        default="CUSTOMER",
        groups="base.group_system",
        help="Form-POST parameter name for the customer / account "
        "number. Defaults to ``CUSTOMER``; common alternatives include "
        "``CUSTNR``, ``KUNDEN_NR``, ``KNDNR``. Leave the generic "
        "``auth_customer_number`` field empty for suppliers that "
        "don't require a customer number (e.g. INDI).",
    )
    oci_param_language = fields.Char(
        string="Language param name",
        default="~Language",
        groups="base.group_system",
        help="Form-POST parameter name for the buyer's session "
        "language. Defaults to the OCI 4.0 convention ``~Language``; "
        "TVH and a few other suppliers expect lowercase ``language``. "
        "Value sent is the 2-letter ISO 639-1 code derived from the "
        "current user's ``res.lang`` (``nl_NL`` → ``nl``). Clear this "
        "field to skip the language param entirely for suppliers that "
        "don't honor it.",
    )
    # -- Inbound cart-field mapping (NEW_ITEM-<name> -> Odoo) -------------
    # Which OCI cart field feeds each Odoo concept. Vendor-specific, so
    # set per supplier in the preset; a customer can clear any of these
    # to disable that particular mapping (e.g. they maintain their own
    # barcodes / nomenclature). The purchase side (``punchout_oci_purchase``)
    # reads these names -- keeping the vendor config as data, not code.
    oci_barcode_field = fields.Char(
        string="Barcode source field",
        default="VENDORMAT",
        groups="base.group_system",
        help="OCI cart field (NEW_ITEM-<name>) holding the product's "
        "GTIN/EAN, copied to the barcode of auto-created products. "
        "Defaults to ``VENDORMAT``; some suppliers carry the GTIN in a "
        "different field. Clear it to disable barcode mapping entirely "
        "(e.g. customers who maintain their own barcodes).",
    )
    oci_vat_field = fields.Char(
        string="VAT-percentage source field",
        default="VATPERCENTAGE",
        groups="base.group_system",
        help="OCI cart field (NEW_ITEM-<name>) holding the line's VAT "
        "percentage. When it disagrees with the tax Odoo's product / "
        "fiscal-position chain would apply, a matching-rate purchase tax "
        "is forced (handles reduced / zero-rate items). Clear it to "
        "always trust the product / fiscal-position chain instead.",
    )
    oci_hook_param = fields.Char(
        string="HOOK_URL parameter name",
        default="HOOK_URL",
        required=True,
        groups="base.group_system",
        help="Name of the setup-call parameter that carries the return "
        "(HOOK) URL. Defaults to the OCI-standard uppercase ``HOOK_URL``; "
        "some suppliers expect a different case/spelling (e.g. Van Egmond "
        "uses lowercase ``hook_url``). Query-string parameter names are "
        "case-sensitive, so a mismatch means the cart never comes back.",
    )

    @api.model
    def _selection_protocol(self):
        """Add OCI to available protocols."""
        res = super()._selection_protocol()
        res.append(("oci", "OCI"))
        return res
