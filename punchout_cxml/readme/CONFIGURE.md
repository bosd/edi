## Adopting a shipped supplier preset

This module ships pre-configured backend records for cXML
suppliers. They install in archived state so the catalog stays
uncluttered. To adopt one:

1. Open **PunchOut → PunchOut Backends**.
2. Toggle the **Archived** filter on (or open the Archived saved
   search).
3. Pick the supplier you want, click **Unarchive**.
4. On the form (Advanced section, system-only):
   - Replace the **From identity** placeholder with the value
     the supplier assigned to your account.
   - Replace the **Shared secret** placeholder with your
     buyer-specific secret.
   - Verify the **To** values match what the supplier
     documents (rare to need changes — these identify the
     supplier, not your account).
5. On the form (Connection section):
   - Link **Partner** (your existing `res.partner` for that
     supplier).
6. Switch the **State** to **Open**.

The "Closed" state is a hard kill-switch (controllers refuse
traffic, `_create_punchout_session` refuses to start) — useful
when retiring a supplier without deleting the historical sessions.

## Configuring a new cXML supplier (no preset yet)

Six fields make a cXML PunchOut connection work:

- **URL.** The supplier's `PunchOutSetupRequest` endpoint.
- **From domain / identity.** Identifies the buyer. Most
  suppliers use `NetworkId` as the domain and assign a
  buyer-specific identity per customer.
- **To domain / identity.** Identifies the supplier.
  Typically `DUNS` + the supplier's DUNS number — same value
  for every customer connecting to them.
- **Shared secret.** Authenticates the buyer to the supplier.
  Buyer-specific.

The Connection section also has the buyer-side defaults: User
agent and Deployment mode (`test` / `production`). These rarely
need changes per supplier.

When you've got a supplier working, please open a PR adding a
preset record to `data/supplier_presets.xml` and a row to the
table below.

## Test Connection

cXML backends support a **Test Connection** button on the form
that round-trips a real `PunchOutSetupRequest` and verifies the
supplier responds with a valid `PunchOutSetupResponse`. Use it
after entering credentials to catch wrong-URL / wrong-secret
errors before exposing the backend to purchasers.

## Known suppliers

> Community-curated, not endorsed. Each entry reflects the public
> documentation of the supplier at the time of contribution; APIs
> change. Verify against the supplier's current docs before going
> live, and PR fixes when they drift.

| Logo | Supplier | Country | Industry | Notes | Preset |
|---|---|---|---|---|---|
| ![Fabory](../static/description/suppliers/fabory.png) | Fabory | NL / EU | Fasteners, fixings, industrial supply | `NetworkId` From, `DUNS` To = `404789992`. Demo credentials available — see `demo/fabory_demo.xml`. | ✅ shipped (replace `from_identity` + `shared_secret` after registering with Fabory) |

To add an entry: create the preset under
`data/supplier_presets.xml`, optionally add a `demo/<supplier>_demo.xml`
record with public demo credentials for runboat, then add a row
above with the docs link in the description.
