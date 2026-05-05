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

    @api.model
    def _selection_protocol(self):
        """Add OCI to available protocols."""
        res = super()._selection_protocol()
        res.append(("oci", "OCI"))
        return res
