# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections.abc import Iterable

from odoo import fields, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    product_url_template = fields.Char(
        string="Product URL Template",
        help=(
            "URL template the supplier exposes for individual product "
            "pages. ``{vendor_code}`` is substituted with the value of "
            "``product.supplierinfo.product_code``. Example: "
            "``https://eshop.tvh.com/parts/{vendor_code}``. Used by the "
            "'Open at supplier' button on product forms — the lookup is "
            "purely a deep-link, no punchout session is initiated."
        ),
    )
    has_punchout_backend = fields.Boolean(
        compute="_compute_has_punchout_backend",
        search="_search_has_punchout_backend",
        help=(
            "True when this partner has at least one open punchout "
            "backend. Drives the Browse Supplier Catalog button and the "
            "'Punchout Supplier' filter on the contacts search view. "
            "Deliberately NOT gated on supplier_rank: a punchout vendor "
            "may book its POs on a sibling contact and so carry "
            "supplier_rank 0 (e.g. a group parent), yet its backend — "
            "and therefore the catalog — is perfectly usable."
        ),
    )

    def _compute_has_punchout_backend(self):
        # Non-stored: resolved live from the punchout.backend table on
        # each read. A backend is not a field on res.partner, so there is
        # nothing on the partner to @api.depends on; the value is simply
        # recomputed whenever it is read. Purely backend-existence based
        # (see the field help for why supplier_rank is not part of it).
        for rec in self:
            rec.has_punchout_backend = bool(rec.id and rec._find_punchout_backend())

    def _search_has_punchout_backend(self, operator, value):
        # Odoo 19's domain optimizer normalises boolean-field leaves to
        # the ``in`` / ``not in`` forms before the field's search method
        # is called, and the value arrives as an ``OrderedSet`` (Odoo's
        # own type, not a builtin set) — so test membership by iterating,
        # not with ``isinstance(value, set)``. We still accept the plain
        # ``=`` / ``!=`` a hand-written domain might use.
        if operator in ("in", "not in"):
            if isinstance(value, Iterable) and not isinstance(value, str):
                wants_true = any(bool(v) for v in value)
            else:
                wants_true = bool(value)
            positive_op = operator == "in"
        elif operator in ("=", "!="):
            wants_true = bool(value)
            positive_op = operator == "="
        else:
            # Internal programming error (a bad domain), not user-facing —
            # no translation needed.
            raise ValueError(
                f"Unsupported operator {operator!r} for has_punchout_backend"
            )
        partner_ids = (
            self.env["punchout.backend"]
            .search([("state", "=", "open"), ("partner_id", "!=", False)])
            .partner_id.ids
        )
        # "partners with a backend" is wanted when the truthiness we're
        # matching lines up with the operator's polarity: (= True),
        # (in [True]), (!= False), (not in [False]) all select them; the
        # four inverses select "partners without one".
        wants_backend = wants_true == positive_op
        return [("id", "in" if wants_backend else "not in", partner_ids)]

    def _find_punchout_backend(self):
        """Return the (single) open punchout backend for this partner.

        Returns an empty recordset if none configured. Multiple-backend
        scenarios (e.g. industrial + agricultural at TVH) are out of
        scope for the simple "Browse" buttons; they'd want a wizard,
        which is on the roadmap.
        """
        self.ensure_one()
        return self.env["punchout.backend"].search(
            [
                ("partner_id", "=", self.id),
                ("state", "=", "open"),
            ],
            limit=1,
        )

    def action_open_punchout_catalog(self):
        """Browse this supplier's punchout catalog (no PO context)."""
        self.ensure_one()
        backend = self._find_punchout_backend()
        if not backend:
            raise UserError(
                self.env._(
                    "No open punchout backend is configured for "
                    "supplier %(name)s. Configure one under PunchOut → "
                    "Backends and set its state to Open.",
                    name=self.display_name,
                )
            )
        return (
            self.env["punchout.session"]
            .with_context(punchout_backend_id=backend.id)
            ._redirect_to_punchout()
        )
