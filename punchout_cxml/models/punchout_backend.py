# Copyright 2023 ACSONE SA/NV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PunchoutBackend(models.Model):
    _inherit = "punchout.backend"

    # cXML-specific credential fields
    from_domain = fields.Char(
        string="From domain",
        groups="base.group_system",
        help="cXML From credential domain (e.g., 'NetworkId').",
    )
    from_identity = fields.Char(
        string="From identity",
        groups="base.group_system",
        help="cXML From credential identity.",
    )
    to_domain = fields.Char(
        string="To domain",
        help="cXML To credential domain.",
    )
    to_identity = fields.Char(
        string="To identity",
        groups="base.group_system",
        help="cXML To credential identity.",
    )
    shared_secret = fields.Char(
        string="Shared secret",
        groups="base.group_system",
        help="cXML authentication shared secret.",
    )
    user_agent = fields.Char(
        string="User agent",
        help="User agent string for cXML requests.",
    )
    deployment_mode = fields.Char(
        string="Deployment mode",
        help="cXML deployment mode: 'test' or 'production'.",
    )

    # cXML DTD validation
    cxml_version = fields.Char(
        string="cXML Version",
        default="1.2.008",
        help="cXML DTD version.",
    )
    dtd_file = fields.Binary(
        string="DTD File for validation",
        groups="base.group_system",
        help="Optional DTD file for response validation.",
    )
    dtd_filename = fields.Char(
        groups="base.group_system",
    )

    def _get_domain_and_identity(self, credential_type):
        """Get cXML credential domain and identity."""
        self.ensure_one()
        if credential_type in ("From", "Sender"):
            return self.from_domain, self.from_identity
        if credential_type == "To":
            return self.to_domain, self.to_identity
        return False, False

    def _get_cxml_version(self):
        self.ensure_one()
        return self.cxml_version

    def _get_cxml_dtd_declaration(self):
        self.ensure_one()
        version = self._get_cxml_version()
        dtd_link = f"http://xml.cxml.org/schemas/cXML/{version}/cXML.dtd"
        declaration = f'<!DOCTYPE cXML SYSTEM "{dtd_link}">'
        return declaration
