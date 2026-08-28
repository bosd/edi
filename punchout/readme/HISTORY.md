## 19.0.1.5.0 (2026-08)

- [FIX] Backend kanban logos are no longer stretched. The ``image``
  widget always adds Bootstrap ``img-fluid`` (``height:auto``), which
  fought the fixed-box class and left wide logos stretched in the kanban
  (the form view was fine because it passes explicit size options). The
  kanban now uses a plain ``<img>`` with inline ``max-width``/
  ``max-height`` and no forced dimensions, so the browser preserves the
  aspect ratio.

## 19.0.1.4.0 (2026-08)

- [ADD] ``punchout.backend`` now inherits ``mail.activity.mixin`` so
  activities can be scheduled on backends (used by the
  ``punchout_purchase`` 'request setup' adoption nudge).

## 19.0.1.3.0 (2026-08)

- [ADD] ``order_transmission`` on the backend (manual / email / cXML /
  REST / portal) — declares how a confirmed PO actually reaches the
  supplier, since punchout itself only builds the draft PO. Set per
  supplier in the preset; ``punchout_purchase`` surfaces it to the
  purchaser on the PO chatter so it's clear whether/how the order is
  sent. The selection is extensible via ``_selection_order_transmission``.

## 19.0.1.2.6 (2026-08)

- [FIX] Backend kanban logos kept their aspect ratio: the image widget
  renders at the field's 128x128 pixel size, so `o_image_64_max` (max
  dimensions only, no `object-fit`) let wide logos (Dell, Conrad, Fabory,
  Phoenix, Kramp) stretch vertically to fill the square. Switched both the
  main and supplier-picker kanbans to `o_image_64_contain` (fixed 64x64 box
  with `object-fit: contain`), which letterboxes instead of stretching.

## 18.0.1.0.0 (2026)

- [MIG] Migration to Odoo 18.0.
- [IMP] `punchout.uom.mapping` now resolves supplier UoM codes through a
  6-tier chain: backend → supplier → global → UNECE → uom name → caller
  default.
- [IMP] Ship `data/uom_mapping_data.xml` with common non-UNECE codes as
  global defaults (STUECK, ST, STK, PC, PCS, EACH, KG, M, L).
- [IMP] Optional `supplier_id` scope on `punchout.uom.mapping`; both
  scopes (backend, supplier) are now optional.
- [FIX] `_get_browser_form_post_url` now produces RFC-clean URLs
  (no double slashes, no trailing slash before the query string).
- [IMP] Stored `name` field on `punchout.session` so Many2one displays
  show "Backend / 2026-04-26 14:02" instead of "punchout.session,42".
- [IMP] `punchout.backend` inherits `mail.thread` and tracks changes
  to state, protocol, URL, callback URL and session duration.
- [IMP] Smart button on the backend form opens the filtered list of
  sessions for that backend.
- [FIX] Session form's "Received" pane is hidden when
  `setup_request_response` is empty — only cXML actually fills it,
  so the pane was permanently blank for OCI/IDS sessions.
- [IMP] `session_retention_days` field on backend (default 90) +
  daily cron `_gc_punchout_sessions` that vacuums old sessions.
  Previous behaviour: the table grew without bound.
- [IMP] `max_response_size` field on backend (default 1 MiB) +
  `_check_response_size` helper used by the protocol controllers
  to reject oversized supplier payloads.
- [ADD] Dutch translation.

## 13.0.1.0.0 (2023-09-26)

- [ADD] First version.
