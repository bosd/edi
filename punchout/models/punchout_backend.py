# Copyright 2023 ACSONE SA/NV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class PunchoutBackend(models.Model):
    _name = "punchout.backend"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "PunchOut Backend"
    _name_unique = models.Constraint(
        "unique(name)",
        "This PunchOut backend already exists.",
    )

    name = fields.Char(
        required=True,
        tracking=True,
    )
    description = fields.Char(
        required=True,
        tracking=True,
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
        help=(
            "Archived backends are hidden from default views. Used to "
            "park shipped supplier presets that haven't been adopted "
            "yet — managers unarchive the ones they want to set up."
        ),
    )
    image_128 = fields.Image(
        max_width=128,
        max_height=128,
        help=(
            "Supplier logo shown on the backend kanban tile. Bundled "
            "with shipped presets so the catalog looks polished from "
            "first install; managers can replace it."
        ),
    )
    auth_username = fields.Char(
        string="Username",
        tracking=True,
        help=(
            "Generic supplier-login username. Per-protocol session-"
            "setup code maps this onto whatever form-param name the "
            "supplier expects (USERNAME / USER / LOGIN / etc.). Most "
            "OCI / IDS suppliers fit this trio of generic credentials; "
            "the protocol-specific escape hatch (e.g. "
            "``oci_custom_parameters``) stays available for the long "
            "tail."
        ),
    )
    auth_password = fields.Char(
        string="Password",
        help=(
            "Generic supplier-login password. Stored plain-text; "
            "protect via field-level groups and DB-level encryption "
            "as appropriate. Intentionally NOT tracked — tracking "
            "would write the cleartext password to the chatter on "
            "every change."
        ),
    )
    auth_customer_number = fields.Char(
        string="Customer Number",
        tracking=True,
        help=(
            "Generic customer / account number. Many suppliers (TVH, "
            "Würth, Hoffmann …) require this alongside username + "
            "password to identify the buyer's contract."
        ),
    )
    protocol = fields.Selection(
        selection="_selection_protocol",
        required=True,
        default="cxml",
        tracking=True,
        help="The punchout protocol used by this backend.",
    )
    url = fields.Char(
        string="URL",
        required=True,
        tracking=True,
    )
    browser_form_post_url = fields.Char(
        string="Browser form post URL",
        help="Exposed URL where the shopping cart must be sent back to.",
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        selection="_selection_state", default="draft", tracking=True
    )
    order_transmission = fields.Selection(
        selection="_selection_order_transmission",
        default="manual",
        string="Order transmission",
        tracking=True,
        help=(
            "How a confirmed purchase order actually reaches this "
            "supplier. Punchout only builds the draft PO in Odoo — it "
            "does NOT place the order. 'Manual' means you send it via "
            "your usual channel; the other options name an integrated "
            "channel (which may be automatic or a button, depending on "
            "the installed modules). Surfaced to the purchaser on the "
            "PO chatter so it's clear whether/how the order is sent."
        ),
    )
    session_duration = fields.Integer(
        string="Maximum session duration",
        default=7200,
        tracking=True,
    )
    session_retention_days = fields.Integer(
        string="Session retention (days)",
        default=90,
        tracking=True,
        help=(
            "Sessions older than this many days are deleted by the "
            "scheduled action 'Punchout: garbage-collect old sessions'. "
            "0 = keep forever (not recommended; cart payloads can be "
            "large and the table grows without bound)."
        ),
    )
    max_response_size = fields.Integer(
        string="Maximum cart payload (bytes)",
        default=1048576,  # 1 MiB
        tracking=True,
        help=(
            "Reject supplier-callback payloads larger than this many "
            "bytes. Protects the receive endpoint from accidental or "
            "malicious flooding. 0 = no limit (not recommended)."
        ),
    )
    uom_mapping_ids = fields.One2many(
        comodel_name="punchout.uom.mapping",
        inverse_name="backend_id",
        string="UoM Mappings",
        help="Map supplier-specific UoM codes to Odoo UoMs.",
    )
    session_ids = fields.One2many(
        comodel_name="punchout.session",
        inverse_name="backend_id",
        string="Sessions",
    )
    session_count = fields.Integer(compute="_compute_session_count")

    def _compute_session_count(self):
        # Group-by query so a backend with thousands of sessions
        # doesn't load every session record into the count.
        data = self.env["punchout.session"]._read_group(
            [("backend_id", "in", self.ids)], ["backend_id"], ["__count"]
        )
        counts = {backend.id: count for backend, count in data}
        for rec in self:
            rec.session_count = counts.get(rec.id, 0)

    def action_view_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Punchout Sessions"),
            "res_model": "punchout.session",
            "view_mode": "list,form",
            "domain": [("backend_id", "=", self.id)],
            "context": {"default_backend_id": self.id},
        }

    def action_setup_form(self):
        """Activate the backend and open its form for credentials.

        Wired to the ``Activate`` button on archived / draft kanban
        tiles. Mirrors Odoo's payment.provider Disabled-tile flow:
        a single click both flips ``active=True`` (if archived) and
        opens the form so the manager can fill in credentials and
        switch the state to Open.

        Idempotent: already-active records are left alone. Live
        records (state=open AND active=True) shouldn't reach this
        button because the kanban hides it for them, but if they
        do we still open the form harmlessly."""
        self.ensure_one()
        if not self.active:
            self.write({"active": True})
        return {
            "type": "ir.actions.act_window",
            "res_model": "punchout.backend",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": {"active_test": False},
        }

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
                    self.env._(
                        "The duration of the session must be greater than 0. %(name)s",
                        name=rec.display_name,
                    )
                )

    @api.model
    def _selection_state(self):
        return [
            ("draft", "Draft"),
            ("open", "Open"),
            ("closed", "Closed"),
        ]

    @api.model
    def _selection_order_transmission(self):
        """How the confirmed PO reaches the supplier. Extensible — a
        module that implements a channel (e.g. ``punchout_cxml_order_send``)
        can append its own option."""
        return [
            ("manual", "Manual / your own channel"),
            ("email", "Email"),
            ("cxml", "cXML OrderRequest"),
            ("rest", "REST API"),
            ("portal", "Supplier portal"),
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
                self.env._(
                    "Browser form post url is not configured on the backend. %(name)s",
                    name=self.display_name,
                )
            )

        return f"{base_url}/{url.rstrip('/')}/{self.id}?db={self.env.cr.dbname}"

    def _check_open_for_traffic(self):
        """Refuse incoming supplier traffic when the backend isn't
        live. Called from the protocol controllers as the first
        line of defence after backend lookup.

        ``draft`` = configuration in progress, never live yet.
        ``closed`` = decommissioned, must not silently keep
        accepting carts. Either way: refuse and log.

        Raises ``UserError`` (the controller catches and converts
        into a redirect to the backend's fallback URL so the user
        gets a clean message instead of a 500)."""
        self.ensure_one()
        if self.state != "open":
            raise UserError(
                self.env._(
                    "Punchout backend %(name)s is not open (current "
                    "state: %(state)s). Set the backend to 'Open' "
                    "before exposing it to suppliers.",
                    name=self.display_name,
                    state=self.state,
                )
            )

    def _check_response_size(self, payload):
        """Raise ``UserError`` if ``payload`` exceeds the backend's
        configured ``max_response_size``. Called from the protocol
        controllers as a first-line guard against accidental or
        malicious flooding of the receive endpoint. ``max_response_size=0``
        disables the check."""
        self.ensure_one()
        cap = self.max_response_size
        if cap and payload is not None and len(payload) > cap:
            raise UserError(
                self.env._(
                    "Punchout cart payload (%(size)s bytes) exceeds the "
                    "configured limit of %(cap)s bytes for backend "
                    "%(name)s.",
                    size=len(payload),
                    cap=cap,
                    name=self.display_name,
                )
            )

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
