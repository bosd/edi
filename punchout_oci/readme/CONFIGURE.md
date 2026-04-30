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

Each row's logo links to the same PNG stored under
`static/description/suppliers/`, also loaded into the preset's
`image_128` field for the kanban tile — see
[that directory's README](../static/description/suppliers/README.md)
for the conventions and how to add a logo for an existing preset.

| Logo | Supplier | Country | Industry | Auth params | Preset |
|---|---|---|---|---|---|
| ![INDI](../static/description/suppliers/indi.png) | [INDI](https://www.indi.nl/nl-nl/slim-inkopen/erp-connecties/oci-punchout) | NL | Industrial supply | `USERNAME` + `PASSWORD` (no customer number) | ✅ shipped |
| ![DiscountOffice](../static/description/suppliers/discount_office.png) | [DiscountOffice](https://oci.discountoffice.nl/docs/default/configure) | NL | Office supplies | `username` + `password` (lowercase, no customer number); `NEW_ITEM-CUST_FIELD1` = VAT percent on cart return | ✅ shipped |
| ![Phoenix Contact](../static/description/suppliers/phoenix_contact.png) | [Phoenix Contact](https://assets.phoenixcontact.com/file/6cdb9294-a10c-4032-ab0a-1c5c9044c324/media/original?Dokumentation_Punchout_V1_EN.pdf) | DE | Industrial automation / electrical | `USERNAME` + `PASSWORD` (no customer number); `NEW_ITEM-MATGROUP` = eCl@ss 11.0; `NEW_ITEM-CUST_FIELD1` = delivery date | ✅ shipped |
| ![Kramp](../static/description/suppliers/kramp.png) | [Kramp](https://developer.kramp.com/oci) | NL / EU | Agricultural / forestry / earthmoving parts | `logonId` only — no password (Kramp validates by HOOK_URL domain registered with their consultant); `NEW_ITEM-EXT_QUOTE_ID` and `NEW_ITEM-CUST_FIELD5` echoed back per line | ✅ shipped (URL is per-customer; replace the example URL after Kramp registers your domain) |
| ![TVH](../static/description/suppliers/tvh-parts.png) | TVH | BE / global | Forklift / material-handling parts | `username` + `password` (lowercase, no customer number) | ✅ shipped (Industrial URL by default; switch URL for Agricultural account) |
| ![Dell](../static/description/suppliers/dell.png) | [Dell PremierConnect](https://www.delltechnologies.com/asset/en-pk/solutions/premier-solutions/selling-competitive/dell-premierconnect-b2b-mappingspecs-oci.pdf) | US / global | IT hardware | `user_id` + `password` (snake-case username, no customer number); requires `operation_type=create` in vendor params | ✅ shipped (preview URL by default; replace with Dell-provisioned production endpoint after activation) |

To add an entry: create the preset under
`data/supplier_presets.xml`, then add a row above with the
`auth_*` column filled in and a link to the supplier's public
docs in the description.
