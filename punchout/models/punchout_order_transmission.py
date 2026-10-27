# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PunchoutOrderTransmission(models.Model):
    """A channel by which a confirmed purchase order reaches the supplier.

    Each channel is a record so that:

    * a backend can declare *which* channels its supplier actually
      supports (``punchout.backend.supported_transmission_ids``), and the
      ``order_transmission_id`` dropdown is filtered to that set — a
      supplier can never be assigned a channel it does not accept;
    * the module that *implements* a channel owns its record. Base ships
      the universal informational ones (``manual``, ``email``); a channel
      module contributes its own (e.g. ``punchout_cxml_order_send`` ships
      ``cxml``, ``punchout_rest_order_send`` ships ``rest``) and links it
      to the presets that support it.
    """

    _name = "punchout.order.transmission"
    _description = "PunchOut Order Transmission Channel"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Stable technical identifier (e.g. 'manual', 'email', 'cxml').",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        "unique(code)",
        "This order transmission code already exists.",
    )
