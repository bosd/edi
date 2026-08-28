## 19.0.1.9.0 (2026-08)

- [IMP] Move the Cart Field Mappings editor into the backend notebook as
  its own tab (next to UoM Mappings), instead of an inline group — the
  two "supplier-data mapping" tables now live together. Manager-gated.

## 19.0.1.8.0 (2026-08)

- [ADD] **Cart field-mapping framework**. New ``punchout.field.mapping``
  (with a ``punchout.value.mapping`` lookup table) lets each backend map
  supplier-specific cart fields onto the auto-created product — because
  the same datum lands in a different cart field per vendor (Van Egmond
  returns the GTIN in ``CUST_FIELD1``, another OCI vendor in
  ``VENDORMAT``). The engine is protocol-agnostic: OCI and cXML each
  flatten a cart line to ``{source_field: value}`` and the rules do the
  rest. Core targets: ``barcode`` (GTIN-validated), ``image`` (fetched
  from a cart-supplied URL — https/size/content-type guarded),
  ``description``, ``product_code`` and a deferred ``unspsc_category``.
  Values can be used directly or translated through a per-rule lookup
  table (supplier code → Odoo value). Rules run on both new products and
  re-punchout matches; each target fills only when empty unless the rule
  is set to overwrite, so manual corrections survive. Targets are
  extensible — optional-module targets (e.g. brand) ship as bridge
  add-ons (see ``punchout_product_brand``), keeping this module free of
  optional dependencies.

## 19.0.1.7.0 (2026)

- [ADD] Punchout adoption nudge: on a supplier's contact form and its
  POs, when a punchout backend is linked but not yet activated, buyers
  see an info banner and a one-click **Request punchout setup** button
  that raises a To-Do activity for the new **Punchout Manager** group.
  The hint is hidden from managers and can be suppressed per backend
  (``punchout_hide_setup_hint``) for deliberately-parked backends.

## 19.0.1.6.0 (2026)

- [ADD] Post a chatter note on the punchout-created PO stating the
  backend's ``order_transmission`` method (manual / email / cXML / REST /
  portal), so the purchaser knows whether confirming the PO actually
  sends it to the supplier or whether they must place it themselves.

## 19.0.1.5.0 (2026)

- [ADD] "Punchout Supplier" filter on the contacts search view — lists
  the vendors we have a punchout connection with (usually the preferred
  suppliers). Backed by making `has_punchout_backend` searchable.
- [FIX] The Browse-Catalog button on the contact form no longer requires
  `supplier_rank > 0`. A punchout vendor may book its POs on a sibling
  contact and so carry `supplier_rank 0` (e.g. a group parent) while its
  backend — and catalog — is perfectly usable; the button (and the flag)
  now depend on the open backend alone.

## 19.0.1.4.0 (2026)

- [ADD] New `_post_punchout_session_processed(order, new_lines)`
  hook fired at the very end of `process()` (after PO create/append
  and chatter warnings). Empty in base — supplier-specific glue
  modules override it to fire follow-up enrichment, batch inquiries,
  ASN polling, etc., without monkey-patching `process()` itself.

## 18.0.1.0.0 (2026)

- [MIG] Migration to Odoo 18.0.
- [FIX] Surface `partner_id`, `company_id`, `product_category_id` and
  `auto_create_products` on the backend form view (the model carried
  these fields but the form never showed them).
- [IMP] Punchout smart button on PO now counts every distinct session
  that contributed lines (not just the originating one) and opens a
  list view when more than one is involved.
- [FIX] PO and chatter messages produced by the supplier-callback
  auto-process are attributed to the session's `user_id` (the
  purchaser who initiated the punchout) instead of the sudo user.
- [FIX] Hide the Punchout smart button and PO-line "Punchout Session"
  column for users without `base.group_system`, so non-admins don't
  see a button that throws an access error on click.
- [IMP] When auto-process fails, post the exception as a chatter
  message on the session (and on the pre-linked PO when set), so
  the purchaser is notified next to the affected record instead of
  having to read server logs.
- [ADD] `USAGE.md` documenting all the new entry points (Browse
  Supplier Catalog, Open at supplier, auto-process, UoM warnings).
- [IMP] Currency-mismatch chatter warning on the PO when the cart's
  supplier prices are in a different currency than the PO's
  pricelist resolved to. Odoo stores raw cart numbers as
  `price_unit`, so a silent currency drift is invisible without
  this hint.
- [FIX] Hide the "Browse supplier catalog" buttons (PO header, PO
  line area, and vendor form smart button) when the vendor has no
  open punchout backend. Previously the button appeared on every
  draft PO; clicking on a non-punchout vendor raised a UserError —
  now the affordance only shows when it's actionable.
- [FIX] System-user attribution for the supplier-callback path:
  re-enter ``write()`` under OdooBot (SUPERUSER) when ``env.user``
  is empty (auth=none controller path). Avoids the
  ``Expected singleton: res.users()`` crash deep in the
  product-create chain and attributes the state-tracking message to
  OdooBot rather than "unknown user". Per-line / per-PO chatter
  attribution to the punchout-initiating user (``session.user_id``)
  is preserved via ``with_user(author)`` for the actual writes.
- [IMP] Configurable auto-created product defaults on the backend:
  ``default_product_type`` (Goods / Service), ``default_is_storable``
  (track inventory) and ``default_tracking`` (none / lot / serial).
  Replaces the previously hardcoded ``type="consu"`` so spare-parts
  vendors can default to storable inventory in one config knob.
  Stock-aware fields (``is_storable``, ``tracking``) are silently
  ignored when the ``stock`` module isn't installed.
