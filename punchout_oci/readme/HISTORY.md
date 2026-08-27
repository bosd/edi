## 19.0.1.4.0 (2026)

- [ADD] Per-backend inbound cart-field mapping: ``oci_barcode_field``
  (default ``VENDORMAT``) and ``oci_vat_field`` (default
  ``VATPERCENTAGE``) declare which OCI ``NEW_ITEM-<name>`` field feeds
  the product barcode and the line VAT. Vendor-specific, so set in the
  preset; clear either to disable that mapping (e.g. customers keeping
  their own barcodes). Consumed by ``punchout_oci_purchase``.

## 19.0.1.3.0 (2026)

- [ADD] **DESTIL** OCI 4.0 supplier preset (technical supplies / MRO, NL)
  with logo. Ships the fixed catalog parameters DESTIL require
  (``OkCode``, ``~TARGET``, ``~CALLER``, ``SERVICE``) via
  ``oci_custom_parameters``; archived until credentials are filled in.

## 19.0.1.2.1 (2026)

- [FIX] Expose the `oci_param_language` field on the backend form so
  managers can adjust the language-param name (or clear it to skip
  the splice) without dropping into a server-action — was added in
  19.0.1.2.0 but never wired into the OCI Settings group.
- [ADD] Test coverage for the session-language splice: default
  `~Language` mapping, per-supplier override (lowercase `language`),
  skip-when-cleared, and `oci_custom_parameters` override-wins.

## 19.0.1.2.0 (2026)

- [ADD] Pass the buyer's session language to the supplier's catalog
  on punchout-setup. New `oci_param_language` field on the backend
  (default `~Language` per OCI 4.0; TVH preset overrides to
  lowercase `language`); the URL builder splices the user's
  2-letter ISO 639-1 code (`nl_NL` → `nl`). Saves a manual language
  switch on the supplier side and lets language-sensitive suppliers
  (TVH) pick the right UoM / description set up front. Clear the
  field on the backend to skip the param entirely.

## 18.0.1.0.0 (2026)

- [MIG] Migration to Odoo 18.0. Original OCI protocol implementation by
  Hunki Enterprises BV (Holger Brunn).
- [IMP] Add OCI 4.0 to `oci_version` selection (label only, no
  4.0-specific functions yet — see ROADMAP).
- [FIX] HOOK_URL now carries a `punchout_session_token` query param
  (the session's buyer cookie) and the receive controller matches
  the returning cart on it. Previous behaviour matched "most recent
  draft session for backend", which mis-routed concurrent sessions.
- [IMP] Cart-payload size cap (configurable on backend) +
  `SELECT ... FOR UPDATE` lock on the matched session +
  `[punchout.oci.*]` log prefix for ops triage.
