# Copyright 2023 ACSONE SA/NV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PunchoutBackend(models.Model):
    _name = "punchout.backend"
    _description = "PunchOut Backend"
    _sql_constraints = [
        ("name_unique", "unique(name)", _("This PunchOut backend already exists."))
    ]

    name = fields.Char(
        required=True,
    )
    description = fields.Char(
        required=True,
    )
    protocol = fields.Selection(
        selection="_selection_protocol",
        required=True,
        default="cxml",
        help="The punchout protocol used by this backend.",
    )
    url = fields.Char(
        string="URL",
        required=True,
    )
    browser_form_post_url = fields.Char(
        string="Browser form post URL",
        help="Exposed URL where the shopping cart must be sent back to.",
        required=True,
    )
    state = fields.Selection(selection="_selection_state", default="draft")
    session_duration = fields.Integer(
        string="Maximum session duration",
        default=7200,
    )
    uom_mapping_ids = fields.One2many(
        comodel_name="punchout.uom.mapping",
        inverse_name="backend_id",
        string="UoM Mappings",
        help="Map supplier-specific UoM codes to Odoo UoMs.",
    )

    @api.model
    def _selection_protocol(self):
        """Return available protocols. Extended by protocol modules."""
        return [
            ("cxml", "cXML"),
        ]

    @api.constrains("session_duration")
    def _check_session_duration(self):
        for rec in self:
            if rec.session_duration <= 0:
                raise ValidationError(
                    _(
                        "The duration of the session must be greater than 0. {name}"
                    ).format(name=rec.display_name)
                )

    @api.model
    def _selection_state(self):
        return [
            ("draft", _("Draft")),
            ("open", _("Open")),
            ("closed", _("Closed")),
        ]

    def _get_browser_form_post_url(self):
        """Build the full browser form post URL."""
        self.ensure_one()
        url = self.browser_form_post_url
        if url and (url.startswith("http://") or url.startswith("https://")):
            return url
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        if url and url.startswith("/"):
            url = url[1:]
        if not url:
            raise UserError(
                _("Browser form post url is not configured on " "the backend. %(name)s")
                % {"name": self.display_name}
            )

        return "/".join([base_url, url, str(self.id), f"?db={self.env.cr.dbname}"])

    def _check_access_backend(self):
        """
        Inherit this method to check if current user can access
        the backend website
        """
        return True

    def redirect_to_backend(self):
        self.ensure_one()
        self._check_access_backend()
        return (
            self.env["punchout.session"]
            .with_context(
                punchout_backend_id=self.id,
            )
            ._redirect_to_punchout()
        )

    def _get_redirect_url(self):
        self.ensure_one()
        return "/web"
