## First-class product Classification field

cXML `ItemDetail/Classification` carries one or more standard product
codes (UNSPSC, eCl@ss, NAICS, supplier-internal taxonomies) tagged by
the `domain` attribute. Today this module appends them as a labelled
footer to `product.description_purchase`:

```
[Classification]
UNSPSC: 31162400
eCl@ss: 23-23-19-01
```

That gives the buyer the information at point-of-purchase (visible on
the PO line description) without inventing a schema, but it isn't
queryable, doesn't survive product re-imports cleanly, and can't be
mapped to internal product categories.

The proper fix is a generic `product.classification` model (m2m or
o2m on `product.template`) with a `domain` selection (UNSPSC, eCl@ss,
custom) and a free-text `code`. This belongs upstream — either in OCA
`product` or as a dedicated `product_classification` module — because
the same data flows in via EDI imports, supplier feeds, and PIM
syncs, not just punchout. When that module exists, this glue should
write to the structured field and stop touching `description_purchase`.

## PriceBasisQuantity handling

cXML `ItemDetail/PriceBasisQuantity` lets the supplier quote a price
per N units instead of per single unit (e.g. "EUR 12.00 per 100
pieces"). Today this module ignores the element and treats every
`UnitPrice/Money` as price-per-1, which is correct for every supplier
we've round-tripped so far (Fabory's cart sends each line as 1:1).

A robust implementation needs to:

1. Read `PriceBasisQuantity/@quantity` (the conversion factor) and
   `PriceBasisQuantity/UnitOfMeasure` (which may differ from the order
   UoM — e.g. quoted per 100 pieces but ordered as a single carton).
2. Either divide `UnitPrice/Money` by the conversion factor before
   storing on the PO line (simplest, matches Odoo's per-unit price
   semantics), or set `product.uom_po_id` and `product.seller_ids.min_qty`
   so Odoo's own price-per-package logic kicks in (cleaner, but touches
   more product-side configuration and risks collisions when multiple
   suppliers quote the same product with different basis quantities).
3. Round to the product currency's decimal precision after conversion
   to avoid sub-cent drift.

Defer until a real supplier sends a non-1 PriceBasisQuantity. When
they do, prefer option 1 unless the supplier also pushes minimum-order
quantities, in which case option 2 starts paying off.

## cXML OrderRequest sender (post-confirmation EDI to supplier)

This module receives the punchout cart and creates a draft PO. Once
the buyer confirms that PO, the order leaves Odoo via email/print
today. Several cXML-capable suppliers also accept the confirmed PO
back as a cXML `OrderRequest` document, closing the loop without
manual paperwork:

- **DiscountOffice** — `POST https://oci.discountoffice.nl/cxml/order`,
  `From/Credential[domain="DiscountOffice"]` with debtor number +
  shared secret obtained from their OCI settings menu.
- **Manutan** — XML order acceptance, exact format / endpoint
  pending (test account requested 2026-05-01).

Implementation sketch (new module, `punchout_cxml_order_send` or
similar, depending on `punchout_cxml_purchase`):

1. New `punchout.backend` field for the OrderRequest endpoint
   (separate from the punchout setup URL — DiscountOffice serves
   cart-return on their punchout host but order-submit on a sibling
   path).
2. A Qweb template for `cXML/Request/OrderRequest` mirroring the
   existing setup-request template — same `Header/From/To/Sender`
   credential block, OrderRequest body built from `purchase.order`
   and its lines.
3. Hook on `purchase.order.button_confirm` (or a new server action
   "Send to supplier as cXML"): render → POST → parse cXML
   `Response/Status/@statusCode`. On 200, flip PO to a new
   tracking state ("Sent to supplier"); on error, surface
   `statusText` in chatter and leave the PO confirmable for retry.
4. Reuse the existing `from_domain` / `shared_secret` credentials
   on the backend — same auth model as the punchout setup.

Fabory does **not** accept cXML orders today (e-PDF only per their
docs). Pick this up once Manutan's test account is live so the
implementation can be validated against two distinct suppliers
before generalising.
