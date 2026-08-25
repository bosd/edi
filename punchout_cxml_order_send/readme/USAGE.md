1. On the PunchOut backend (cXML), tick **Send orders as cXML** and fill the
   **OrderRequest endpoint** the supplier gave you (often different from the
   PunchOut setup URL). Optionally record the supplier's **order email**.
2. On a confirmed purchase order for that supplier, press **Send to supplier
   (cXML)**. The order is rendered as a cXML `OrderRequest` (reusing the
   backend's credentials) and POSTed to the endpoint. The supplier's cXML
   `Response/Status` is checked; on success the PO is stamped *cXML order sent*,
   on rejection the reason is raised and the PO stays sendable for a retry.

A representative message is shipped at
`static/description/sample_orderrequest.xml` for supplier onboarding /
format validation.
