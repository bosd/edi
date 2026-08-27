# Copyright 2023 ACSONE SA/NV
# Copyright 2023 Hunki Enterprises BV
# Copyright 2025 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PunchoutSession(models.Model):
    _inherit = "punchout.session"

    purchase_order_id = fields.Many2one(
        comodel_name="purchase.order",
        string="Purchase Order",
        readonly=True,
        help=(
            "When set BEFORE the cart is received (the user started "
            "the punchout from a draft PO), the returning lines are "
            "appended to this PO instead of creating a new one. "
            "When set AFTER the cart is received, this is the PO that "
            "was created from the session."
        ),
    )

    @api.model
    def _create_punchout_session(self):
        """Pre-link the session to a target PO when one was specified
        via context (set by ``purchase.order.action_open_punchout_catalog``).
        Falls back to the base behaviour (no PO pre-link) when not set.
        """
        session = super()._create_punchout_session()
        target_po_id = self.env.context.get("punchout_target_purchase_order_id")
        if target_po_id:
            session.sudo().purchase_order_id = target_po_id
        return session

    purchase_order_count = fields.Integer(
        compute="_compute_purchase_order_count",
    )

    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = 1 if rec.purchase_order_id else 0

    def action_view_purchase_order(self):
        """Open the related purchase order."""
        self.ensure_one()
        if not self.purchase_order_id:
            raise UserError(self.env._("No purchase order linked to this session."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": self.purchase_order_id.id,
        }

    def action_process(self):
        """When a supplier is configured, "Process" creates the purchase order
        (or appends to a pre-linked PO) instead of just marking the session
        done — the create/append is what the user almost always wants once
        the cart has been received."""
        self.ensure_one()
        if self.state == "to_process" and self.backend_id.partner_id:
            return self.action_create_purchase_order()
        return super().action_process()

    def action_create_purchase_order(self):
        """Create or append a purchase order from the session response.

        If ``purchase_order_id`` is pre-set on the session (the user
        started the punchout from an existing draft PO), the cart's
        lines are appended to that PO. Otherwise a new PO is created.

        All PO writes/creates and chatter posts are performed under
        ``self.user_id`` (the purchaser who initiated the session) so
        the audit trail attributes the work to a real human, not the
        sudo'd context the supplier callback runs in.
        """
        self.ensure_one()
        if self.state != "to_process":
            raise UserError(
                self.env._(
                    "Session must be in 'To Process' state to create a purchase order."
                )
            )
        # The supplier-callback path is ``auth="none"``; ``env.user``
        # there can be the public user OR an empty recordset
        # depending on the Odoo version + how sudo / auth interact.
        # Calling ``with_user(empty)`` is a no-op (returns self
        # unchanged), and the empty-env then poisons the deeper
        # product-create chain (``stock._default_responsible_id``
        # crashes on ``self.env.user._is_superuser()``).
        # Resolution order:
        #   1. session.user_id (the human who clicked the punchout
        #      button — best for audit attribution)
        #   2. env.user (if non-empty)
        #   3. OdooBot / SUPERUSER (system fallback, always exists)
        author = self.user_id or self.env.user
        if not author or not author.id:
            # OdooBot is the right system fallback over a human admin:
            # signals "system action" in the chatter (no confusion
            # with manual admin edits) and runs in superuser mode.
            author = self.env.ref("base.user_root")
        # Run the technical PO create / append under
        # ``with_user(author).sudo()``: the human who started the
        # punchout shows up as ``env.user`` (so the PO's
        # ``create_uid`` and the auto-tracking chatter avatar are
        # the buyer, not OdooBot), AND ``su=True`` bypasses
        # cross-company ACLs.
        #
        # Order matters: ``with_user(author).sudo()`` preserves
        # ``su=True``. The reverse order would reset ``su`` to
        # False because ``Environment(user=...)`` drops the
        # superuser flag when the uid changes — and ACLs would
        # then trip the record rule on ``account.tax`` the moment
        # Odoo computes taxes during PO create.
        #
        # We keep ``with_company`` so default field values
        # (currency, fiscal position, payment terms…) resolve from
        # the BACKEND's company, not the user's default.
        company = self.backend_id._get_company()
        scoped = self.with_user(author).sudo().with_company(company)
        if self.purchase_order_id:
            # Append-to-existing flow (started from a draft PO).
            if self.purchase_order_id.state not in ("draft", "sent"):
                raise UserError(
                    self.env._(
                        "Purchase order %(name)s is no longer editable; "
                        "cannot append lines from a punchout session.",
                        name=self.purchase_order_id.display_name,
                    )
                )
            new_line_cmds = self._tag_lines_with_session(
                self._prepare_purchase_order_lines()
                + self._prepare_protocol_extra_lines()
            )
            if new_line_cmds:
                self.purchase_order_id.with_user(author).sudo().with_company(
                    company
                ).write({"order_line": new_line_cmds})
            self.write({"state": "done"})
        else:
            order = scoped._create_purchase_order_from_response()
            self.write(
                {
                    "purchase_order_id": order.id,
                    "state": "done",
                }
            )
        # Post any cart-vs-product mismatch warnings to the PO chatter
        # so the purchaser sees them before confirming.
        new_lines = self.purchase_order_id.order_line.filtered(
            lambda line: line.punchout_session_id == self
        )
        order_scoped = (
            self.purchase_order_id.with_user(author).sudo().with_company(company)
        )
        self._post_punchout_line_warnings(order_scoped, new_lines, author)
        # Make it clear to the purchaser HOW (or whether) confirming this
        # PO reaches the supplier — punchout only builds the draft PO.
        self._post_punchout_order_transmission_note(order_scoped, author)
        # Generic post-process extension point. Empty in base —
        # supplier-specific glue modules (e.g. ``flc_punchout_tvh``)
        # override this to fire follow-up actions like a batch
        # inquiry that enriches the newly-created products in one
        # quota slot. Failures inside the override MUST be caught
        # there — the cart-import flow should never break because an
        # enrichment call timed out.
        self._post_punchout_session_processed(order_scoped, new_lines)
        return self.action_view_purchase_order()

    def _post_punchout_session_processed(self, order, new_lines):
        """Hook fired after the punchout session is fully processed
        (PO created or appended, chatter warnings posted). ``order``
        is already scoped to the right user / company. Empty in base
        — protocol- and supplier-specific modules override to attach
        follow-up enrichment, ASN polling, etc.

        Pass the FULL order so the override can inspect every line
        (including pre-existing ones); the freshly-added subset is
        in ``new_lines`` for cases where the override only wants to
        operate on the just-arrived items."""

    def _post_punchout_order_transmission_note(self, order, author):
        """Post a chatter note stating how the confirmed order reaches the
        supplier. Punchout only builds the draft PO in Odoo; whether
        confirming it transmits the order (and by which channel) depends
        on the backend's ``order_transmission``. Makes that explicit so a
        purchaser doesn't assume 'confirmed in Odoo' means 'sent'.
        """
        self.ensure_one()
        backend = self.backend_id
        method = backend.order_transmission or "manual"
        label = dict(
            backend._fields["order_transmission"]._description_selection(self.env)
        ).get(method, method)
        supplier = backend.partner_id.display_name or self.env._("the supplier")
        if method == "manual":
            body = Markup(
                self.env._(
                    "<strong>Order transmission: %(label)s.</strong> Built "
                    "from a %(backend)s punchout. Confirming this PO in Odoo "
                    "does <strong>not</strong> send it to %(supplier)s — place "
                    "the order through your usual channel."
                )
            ) % {
                "label": label,
                "backend": backend.display_name,
                "supplier": supplier,
            }
        else:
            body = Markup(
                self.env._(
                    "<strong>Order transmission: %(label)s.</strong> Built "
                    "from a %(backend)s punchout. The order is sent to "
                    "%(supplier)s via %(label)s (see this PO's send "
                    "action/automation)."
                )
            ) % {
                "label": label,
                "backend": backend.display_name,
                "supplier": supplier,
            }
        post_kwargs = {"body": body}
        if author and author.partner_id:
            post_kwargs["author_id"] = author.partner_id.id
        order.message_post(**post_kwargs)

    def _build_line_mismatch_messages(self, line):
        """Return a list of human-readable mismatch warnings for one new line.

        Generic across protocols. Today only the UoM check is
        implemented because that one materially changes ordered
        quantity (Box vs Unit). Price and description differences are
        expected (suppliers send their own values) and don't trigger
        noise. Override / extend in subclasses for protocol-specific
        checks (e.g. cart price wildly above existing supplierinfo).
        """
        self.ensure_one()
        warnings = []
        product = line.product_id
        # The UoM field on PO line was renamed product_uom -> product_uom_id
        # in Odoo 19; tolerate both.
        line_uom = getattr(line, "product_uom_id", None) or getattr(
            line, "product_uom", None
        )
        if line_uom and product and product.uom_id and line_uom != product.uom_id:
            warnings.append(
                self.env._(
                    "%(name)s: cart UoM <strong>%(cart)s</strong> differs "
                    "from the product's primary UoM <strong>%(prod)s</strong>. "
                    "Verify the line quantity before confirming — Odoo "
                    "applies any same-category conversion automatically, "
                    "but cross-category or unmapped supplier UoMs may "
                    "have been silently coerced to the product default.",
                    name=product.display_name,
                    cart=line_uom.display_name,
                    prod=product.uom_id.display_name,
                )
            )
        return warnings

    def _build_currency_mismatch_message(self, order, new_lines):
        """Compare the cart's per-supplier price currency against the
        PO's currency. Returns a single warning string when they
        differ, or ``None``.

        We can't recover the cart's currency from the line itself
        (the cart's currency code lives on the auto-created /
        matched ``product.supplierinfo``), so we read it back from
        the seller for this backend's partner. Important because
        Odoo silently stores raw cart prices on the PO line — if
        the cart sent EUR and the PO is USD, every ``price_unit``
        is now an EUR number masquerading as USD."""
        self.ensure_one()
        partner = self.backend_id.partner_id
        if not (partner and order.currency_id):
            return None
        cart_currencies = set()
        for line in new_lines:
            seller = line.product_id.seller_ids.filtered(
                lambda s, p=partner: s.partner_id == p
            )[:1]
            if seller and seller.currency_id:
                cart_currencies.add(seller.currency_id)
        mismatched = {c for c in cart_currencies if c != order.currency_id}
        if not mismatched:
            return None
        return self.env._(
            "PO currency is <strong>%(po)s</strong> but the cart's "
            "supplier prices are in <strong>%(cart)s</strong>. Odoo "
            "stores raw cart numbers as ``price_unit``, so each line's "
            "price is a %(cart)s value being treated as %(po)s. "
            "Verify the lines (and consider switching the PO's pricelist) "
            "before confirming.",
            po=order.currency_id.display_name,
            cart=", ".join(c.display_name for c in mismatched),
        )

    def _build_protocol_header_messages(self, order, new_lines):
        """Return a list of HTML warning strings about cart-header
        data the supplier sent that Odoo can't represent natively
        (Shipping, Order Costs, Tax/Total mismatches).

        Default empty. Protocol modules (``punchout_cxml_purchase``,
        etc.) override to extract their cart's header fields from
        ``self.response`` and return human-readable summaries that
        the existing chatter helper appends to the warning bullet
        list. Until the system has dedicated handling for shipping
        / order-cost lines, surfacing the values via chatter lets
        the buyer reconcile manually before confirming the PO.
        """
        self.ensure_one()
        return []

    def _post_punchout_line_warnings(self, order, new_lines, author=None):
        """Post one chatter message on the PO bundling all warnings
        from the cart vs the resolved PO/product data — keeps the
        audit trail compact.

        Two classes of check today:
        * per-line UoM mismatch (cart UoM != product's primary UoM)
        * PO-level currency mismatch (cart prices in a different
          currency than the PO's pricelist resolved to)
        Override / extend in subclasses for protocol-specific checks.

        ``author`` (optional, ``res.users``): explicit attribution
        for ``message_post``. Used by ``action_create_purchase_order``
        to route the chatter under the session-initiating human even
        though the technical write runs under SUPERUSER. Falls back
        to the env's default attribution when omitted.
        """
        self.ensure_one()
        if not new_lines:
            return
        all_warnings = []
        for line in new_lines:
            all_warnings.extend(self._build_line_mismatch_messages(line))
        currency_msg = self._build_currency_mismatch_message(order, new_lines)
        if currency_msg:
            all_warnings.append(currency_msg)
        # Protocol-specific extras — cart-header summary (cXML
        # PunchOutOrderMessageHeader: Total, Shipping, Tax,
        # Extrinsic costs), supplier-side metadata that doesn't
        # fit per-line. Empty hook in base; protocol modules
        # override.
        all_warnings.extend(self._build_protocol_header_messages(order, new_lines))
        if not all_warnings:
            return
        # ``Markup`` so the <strong>/<ul>/<code> tags render as HTML
        # in the chatter instead of being shown as escaped text.
        body = Markup(
            self.env._("Punchout cart vs Odoo product data — discrepancies on this PO:")
            + "<ul><li>"
            + "</li><li>".join(all_warnings)
            + "</li></ul>"
        )
        post_kwargs = {"body": body}
        if author and author.partner_id:
            post_kwargs["author_id"] = author.partner_id.id
        order.message_post(**post_kwargs)

    def _tag_lines_with_session(self, line_cmds):
        """Inject ``punchout_session_id`` into every (0, 0, vals) command.

        Called from action_create_purchase_order — done at that layer
        rather than overriding _prepare_purchase_order_lines because
        protocol modules (cxml/oci/ids) override _prepare_ without
        calling super, so an override-based approach silently no-ops
        for those protocols (the most common ones)."""
        tagged = []
        for cmd in line_cmds:
            if isinstance(cmd, list | tuple) and cmd[0] == 0 and len(cmd) == 3:
                vals = {**cmd[2], "punchout_session_id": self.id}
                tagged.append((0, 0, vals))
            else:
                tagged.append(cmd)
        return tagged

    def _create_purchase_order_from_response(self):
        """Create purchase order from response. Override in protocol modules."""
        self.ensure_one()
        backend = self.backend_id
        if not backend.partner_id:
            raise UserError(
                self.env._(
                    "Please configure a supplier on the backend %(name)s.",
                    name=backend.display_name,
                )
            )

        order_vals = self._prepare_purchase_order_vals()
        return self.env["purchase.order"].create(order_vals)

    def _prepare_purchase_order_vals(self):
        """Prepare values for purchase order creation."""
        self.ensure_one()
        backend = self.backend_id
        return {
            "partner_id": backend.partner_id.id,
            "company_id": backend._get_company().id,
            "punchout_session_id": self.id,
            "order_line": self._tag_lines_with_session(
                self._prepare_purchase_order_lines()
                + self._prepare_protocol_extra_lines()
            ),
        }

    def _prepare_protocol_extra_lines(self):
        """Cart-header surcharges materialised as PO lines.

        Default empty. Protocol modules override to extract supplier-
        quoted shipping / order-cost / insurance / etc. amounts from
        the cart header and return ``(0, 0, vals)`` commands so the
        buyer doesn't have to add them by hand. Each charge resolves
        through ``_get_or_create_punchout_charge_product`` so users
        who pre-create a curated service product with the expected
        name keep using their own product.
        """
        self.ensure_one()
        return []

    def _get_or_create_punchout_charge_product(self, charge_name):
        """Resolve the service product used for a cart-header charge
        line (Shipping, Order Costs, Insurance, ...). Looked up by
        exact name first so users who pre-create a curated product
        with that name keep using it; auto-created on first use
        otherwise. Seeds ``supplier_taxes_id`` from the backend
        company's default purchase tax so the resulting PO line picks
        up the same VAT rate as cart-item lines — cXML's ``<Tax>``
        covers items + shipping + extrinsic as one total, and
        suppliers almost always apply the same rate to all of them.
        We seed explicitly rather than relying on the field's
        ``default=`` lambda because ``env.companies`` under the
        auth-none cart-return controller can resolve to a different
        set than the backend's company."""
        self.ensure_one()
        product_name = f"Punchout: {charge_name}"
        Product = self.env["product.product"]
        existing = Product.search([("name", "=", product_name)], limit=1)
        if existing:
            return existing
        company = self.backend_id._get_company()
        vals = {
            "name": product_name,
            "type": "service",
            "purchase_ok": True,
            "sale_ok": False,
            "description_purchase": self.env._(
                "Auto-created by Punchout to capture the supplier's "
                "quoted %(charge)s charge as a PO line.",
                charge=charge_name,
            ),
        }
        default_tax = company.account_purchase_tax_id
        if default_tax:
            vals["supplier_taxes_id"] = [(6, 0, default_tax.ids)]
        default_sale_tax = company.account_sale_tax_id
        if default_sale_tax:
            vals["taxes_id"] = [(6, 0, default_sale_tax.ids)]
        return Product.sudo().with_company(company).create(vals)

    def write(self, vals):
        """Auto-process the cart when state moves to ``to_process``.

        Once the supplier's POST has populated the session and the
        cart is parsed, the user almost never wants the session to sit
        in to_process — they want the PO. Auto-fire
        action_create_purchase_order so the redirect lands the user
        on a PO with the new lines visible. Skips when the backend
        has no supplier configured (manual-review fallback).

        **System-user attribution** for the state-tracking message
        and the auto-process create chain: the supplier-callback
        controller is ``auth="none"``, so ``env.user`` may be empty
        / public. Standard ``mail.thread`` would attribute the
        state-tracking message to "unknown" and the deeper product-
        create chain crashes on
        ``self.env.user._is_superuser()`` (``Expected singleton:
        res.users()``). Switch the env to admin **before** calling
        super so:
          * the tracking message has a real author (admin → renders
            as "Administrator" / "OdooBot" depending on the install)
          * the auto-process flow has ``self.env.user`` = admin,
            avoiding the empty-singleton crash deep in stock's
            ``_default_responsible_id``
        Per-line / per-PO attribution to the punchout-initiating
        user (``session.user_id``) still happens inside
        ``action_create_purchase_order`` via ``with_user(author)``
        for the actual writes — only the system-level entry point
        is admin.

        On failure, surface the error in the session's chatter and
        on the pre-linked PO's chatter so the purchaser is notified
        next to the affected record instead of having to dig through
        server logs."""
        # Detect controller-path writes (env.user is empty OR the
        # public user from an ``auth="none"`` controller) and re-enter
        # under OdooBot's identity. The existing check ``not env.uid``
        # alone wasn't enough: in Odoo 19 ``auth="none"`` resolves
        # ``env.user`` to the public user (truthy uid + truthy
        # recordset), so the re-entry didn't fire and ``mail.thread``
        # attributed the state-tracking message to the public user
        # (renders as "no user" in the chatter).
        # ``_is_internal()`` is the canonical helper for "real Odoo
        # user", excluding both public and portal users — exactly the
        # population we want to redirect to OdooBot. OdooBot
        # (``base.user_root``, the SUPERUSER) is the right choice over
        # a human admin: it signals "system action" in the chatter
        # (avoids confusion with manual admin edits), and
        # ``with_user(SUPERUSER)`` implicitly enables superuser mode
        # (per Odoo docstring: "by convention, the superuser is
        # always in superuser mode") so the deeper product-create
        # chain bypasses any partner / company ACLs that would
        # otherwise resolve env.user to an empty recordset.
        if (
            vals.get("state") == "to_process"
            and not self.env.context.get("skip_punchout_auto_process")
            and (
                not self.env.uid
                or not self.env.user
                or not self.env.user._is_internal()
            )
        ):
            # Pick the human who initiated the punchout
            # (``session.user_id``) so their avatar shows on the
            # state-tracking message in the chatter. Fall back to
            # OdooBot when the session has no user attached.
            #
            # Order matters: ``with_user(author).sudo()`` keeps
            # ``su=True`` AND sets ``uid=author``. The reverse order
            # (``sudo().with_user(author)``) would reset ``su`` to
            # False because ``Environment.__call__(user=...)`` drops
            # the superuser flag when the uid changes. ``su=True``
            # bypasses cross-company ACLs (``account.tax`` record
            # rules etc.); the human attribution is what gives the
            # chatter message a recognisable avatar.
            #
            # State changes typically affect a single session at a
            # time (one cart → one session); for the rare batch
            # case we attribute to the first record's ``user_id``.
            first = self[:1]
            author = (first.user_id if first else False) or self.env.ref(
                "base.user_root"
            )
            return self.with_user(author).sudo().write(vals)
        res = super().write(vals)
        if vals.get("state") == "to_process":
            for rec in self:
                if rec.backend_id.partner_id and not self.env.context.get(
                    "skip_punchout_auto_process"
                ):
                    try:
                        rec.with_context(
                            skip_punchout_auto_process=True
                        ).action_create_purchase_order()
                    except Exception as e:  # noqa: BLE001
                        _logger.warning(
                            "Auto-process of session %s failed; user can "
                            "still click Process manually. Error: %s",
                            rec.display_name,
                            e,
                        )
                        rec._notify_auto_process_failure(e)
        return res

    def _notify_auto_process_failure(self, exc):
        """Post a chatter message on the session and (when pre-linked)
        on the target PO so the purchaser is notified of the failure
        rather than having to discover it from the session staying in
        ``to_process``.

        Defensive: this method is called from the failure branch of
        the auto-process flow, which itself runs from an
        ``auth="none"`` controller. ``env.user`` may be empty or the
        public user. Fall through to OdooBot (SUPERUSER) so the
        chatter post never crashes — losing the notification entirely
        is worse than attributing it to OdooBot.
        """
        self.ensure_one()
        author = self.user_id or self.env.user
        if not author or not author.id:
            author = self.env.ref("base.user_root")
        # Include the session's display name in the body — when several
        # sessions exist for the same partner the chatter on the PO
        # otherwise can't be traced back to a specific session.
        # ``Markup`` so the <strong>/<br/>/<code> tags render as HTML
        # in the chatter rather than being shown as escaped text.
        body = Markup(
            self.env._(
                "Auto-creation of the purchase order failed for punchout "
                "session <strong>%(session)s</strong>. The session "
                "remains in <strong>To Process</strong> — open it and "
                "click Process to retry once the issue is resolved.<br/>"
                "Error: <code>%(err)s</code>",
                session=self.display_name,
                err=exc,
            )
        )
        # Author attribution via ``message_post(author_id=...)`` rather
        # than ``with_user(author).message_post(...)`` — the latter
        # also runs ACL checks under the author, which can fail for the
        # same reason that brought us here (admin lacking the
        # backend's company in ``company_ids``). sudo() bypasses ACLs;
        # author_id sets the visible chatter author.
        post_kwargs = {"body": body}
        if author and author.partner_id:
            post_kwargs["author_id"] = author.partner_id.id
        # Both message_posts wrapped in their own try/except — even the
        # safety-net author resolution can't help if message_post itself
        # raises (e.g. mail module misconfigured). The session stays in
        # to_process and the user can still click Process manually.
        try:
            self.sudo().message_post(**post_kwargs)
        except Exception as inner_exc:  # noqa: BLE001
            _logger.warning(
                "Punchout session %s: failed to post auto-process "
                "failure chatter on the session: %s",
                self.display_name,
                inner_exc,
            )
        if self.purchase_order_id:
            try:
                self.purchase_order_id.sudo().message_post(**post_kwargs)
            except Exception as inner_exc:  # noqa: BLE001
                _logger.warning(
                    "Punchout session %s: failed to post auto-process "
                    "failure chatter on PO %s: %s",
                    self.display_name,
                    self.purchase_order_id.display_name,
                    inner_exc,
                )

    def _prepare_purchase_order_lines(self):
        """Prepare order lines from response. Override in protocol modules."""
        # This should be overridden by protocol-specific modules
        return []

    def _get_redirect_url(self):
        """Redirect to purchase order after processing."""
        self.ensure_one()
        if self.purchase_order_id:
            order_id = self.purchase_order_id.id
            return f"/web#id={order_id}&model=purchase.order&view_type=form"
        return super()._get_redirect_url()
