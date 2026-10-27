# Copyright 2026 Bosd
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRestChannel(TransactionCase):
    def test_rest_channel_record(self):
        """The module ships the generic 'rest' transmission channel,
        active and ordered after the base manual/email channels."""
        channel = self.env.ref(
            "punchout_rest_order_send.transmission_rest",
            raise_if_not_found=False,
        )
        self.assertTrue(channel, "transmission_rest channel record is missing")
        self.assertEqual(channel.code, "rest")
        self.assertTrue(channel.name)
        self.assertTrue(channel.active)
        manual = self.env.ref("punchout.transmission_manual")
        self.assertGreater(channel.sequence, manual.sequence)
