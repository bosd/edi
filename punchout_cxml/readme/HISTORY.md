## 19.0.1.2.1 (2026-08)

- [ADD] Conrad Electronic preset now ships the supplier logo
  (``image_128``), matching Fabory and Manutan — the backend and
  its supplier picker show the Conrad mark out of the box.

## 19.0.1.1.8 (2026-05)

- [ADD] **Conrad Electronic** supplier preset (DE/EU electronics
  + components). Ships archived (``active=False`` /
  ``state=draft``) — adopt by unarchiving and filling in the
  ``REPLACE_ME`` placeholders for ``from_identity`` (your
  NetworkId), ``to_identity`` (Conrad's DUNS, from the
  credentials packet) and ``shared_secret``. Endpoint:
  ``https://oci.conrad.com/AribaRequest.html``. No demo override
  shipped — Conrad doesn't publish a public sandbox profile.

## 18.0.1.0.0 (2026)

- [MIG] Migration to Odoo 18.0. Original cXML protocol implementation by
  ACSONE SA/NV (Thomas Binsfeld, Benjamin Willig).
- [FIX] Drop the session form view inheritance that renamed the
  generic "Setup" / "Response" notebook tabs to "cXML Setup" /
  "cXML Response". The override applied unconditionally, so OCI and
  IDS sessions also showed cXML labels when this module was installed
  alongside others.
- [IMP] Cart-payload size cap (configurable on backend) +
  `SELECT ... FOR UPDATE` lock on the matched session +
  `[punchout.cxml.*]` log prefix for ops triage.
- [ADD] **Test Connection** button on the backend form: sends a real
  `PunchOutSetupRequest` and verifies the supplier responds with a
  valid setup response. Catches wrong URL / wrong credentials /
  expired DTD link before the user sees a confusing redirect failure
  mid-flow.
