## Adopting a shipped supplier preset

This module ships pre-configured backend records for a growing list
of OCI suppliers. They install in archived state so the catalog
stays uncluttered. To adopt one:

1. Open **PunchOut → PunchOut Backends**.
2. Toggle the **Archived** filter on (or open the Archived saved
   search).
3. Pick the supplier you want, click **Unarchive**.
4. On the form:
   - Link **Partner** (your existing `res.partner` for that supplier).
   - Enter **Username** and **Password** (and **Customer Number**
     if the supplier uses one — see the table below).
   - Optionally upload a **Logo** if the shipped one isn't suitable.
5. Switch the **State** to **Open**.
6. The Browse Supplier Catalog button now appears on that partner's
   Purchase Orders, and the supplier shows up on the kanban
   landing view.

The "Closed" state acts as a hard kill-switch (controllers refuse
traffic, `_create_punchout_session` refuses to start) — useful
when retiring a supplier without deleting the historical sessions.

## Configuring a new supplier (no preset yet)

Three things determine whether your supplier works out of the box:

- **The catalog URL.** The full HTTPS URL of the supplier's
  PunchOut catalog endpoint.
- **The auth field names.** Most OCI suppliers use the
  conventional `USERNAME` / `PASSWORD` form-POST parameters. A
  few use lowercase or supplier-specific names. The defaults in
  the **OCI Settings** group cover the common case; override
  per-supplier as needed.
- **Whether a customer number is required.** Set
  `auth_customer_number` and the matching param name (e.g.
  `CUSTNR`, `KUNDEN_NR`) — or leave both empty for suppliers
  that don't use one.

If your supplier needs auth params beyond the
username/password/customer trio (e.g. a session token, an
extra branch ID), use the **Vendor-specific parameters** field
as a query-string escape hatch:
`token=abc123&branch=NL01`. Keys here override the generic-auth
splice on collision.

When you've got a supplier working, please open a PR adding a
preset record to `data/supplier_presets.xml` and a row to the
table below — that's how the catalog grows.

## Known suppliers

> Community-curated, not endorsed. Each entry reflects the public
> documentation of the supplier at the time of contribution; APIs
> change. Verify against the supplier's current docs before going
> live, and PR fixes when they drift.

| Supplier | Country | Industry | Auth params | Preset |
|---|---|---|---|---|
| INDI | NL | Industrial supply | `USERNAME` + `PASSWORD` (no customer number) | ✅ shipped |
| TVH | BE / global | Forklift / material-handling parts | `username` + `password` (lowercase, no customer number) | ✅ shipped (Industrial URL by default; switch URL for Agricultural account) |

To add an entry: create the preset under
`data/supplier_presets.xml`, then add a row above with the
`auth_*` column filled in and a link to the supplier's public
docs in the description.
