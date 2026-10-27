Adds a **REST API** order-transmission channel to PunchOut backends.

PunchOut only builds the draft purchase order in Odoo; the order still has
to reach the supplier by some channel. This module contributes the generic
`rest` channel record so a backend can declare REST as a supported order
transmission. The concrete REST call (endpoint, authentication, payload) is
supplier-specific and lives in the supplier's own integration module, which
links this channel to the presets that support it.
