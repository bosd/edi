Send a **confirmed purchase order** back to the supplier as a cXML
`OrderRequest`, closing the PunchOut loop: browse the supplier catalogue →
cart returns into a draft PO → confirm → the order is transmitted automatically.

Not every cXML supplier accepts orders this way (some are catalogue-only and
take orders by email/EDI), so it is **opt-in per backend** (`Send orders as
cXML`). Suppliers that don't support it (e.g. Fabory, e-PDF only) are unaffected.
