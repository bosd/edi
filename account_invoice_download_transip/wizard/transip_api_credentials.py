# Copyright 2018-2021 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)

try:
    import transip
except ImportError:
    logger.debug("Cannot import transip")


class TransipApiCredentials(models.TransientModel):
    _name = "transip.api.credentials"
    _description = "Generate Transip API credentials"

    download_config_id = fields.Many2one(
        "account.invoice.download.config",
        string="Download Config",
        readonly=True,
        required=True,
    )
    # endpoint = fields.Selection(
    # "_transip_get_endpoints", string="Endpoint", default="ovh-eu"
    # )
    application_key = fields.Char(string="Application Key")
    transip_login = fields.Char(string="Application Login")
    application_url = fields.Char(string="Application URL", readonly=True)
    validation_url = fields.Char(string="Validation URL", readonly=True)
    consumer_key = fields.Char(string="Consumer Key", readonly=True)
    validation_url_ok = fields.Boolean(string="Validation URL Done")
    state = fields.Selection(
        [
            ("step1", "Step1"),
            ("step2", "Step2"),
            ("step3", "Step3"),
        ],
        string="State",
        readonly=True,
        default="step1"
    )

    # @api.model
    # def _transip_get_endpoints(self):
    # return self.env["account.invoice.download.config"]._transip_get_endpoints()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        assert self._context.get("active_model") == "account.invoice.download.config"
        download_config = self.env["account.invoice.download.config"].browse(
            self._context["active_id"]
        )
        res["download_config_id"] = download_config.id
        # if download_config.transip_endpoint:
        # res["endpoint"] = download_config.transip_endpoint
        return res

    def action_continue_wizard(self):
        self.ensure_one()
        xmlid = "account_invoice_download_transip.transip_api_credentials_action"
        action = self.env["ir.actions.act_window"]._for_xml_id(xmlid)
        action["res_id"] = self.id
        return action

    def run_step1(self):
        self.ensure_one()
        # assert self.endpoint
        # https://api.transip.nl/v6/auth # manually create api keys
        # endpoint2appurl = {
        # "transip-nl": "https://api.transip.nl/v6/",
        # "transip-eu": "https://api.transip.eu/v6/",
        # }
        # self.write(
        # {
        # "application_url": endpoint2appurl[self.endpoint],
        # "state": "step2",
        # }
        # )
        return self.action_continue_wizard()

    def run_step2(self):
        self.ensure_one()
        if not self.application_key or not self.transip_login:
        # or not self.endpoint
            raise UserError(
                _(
                    "The endpoint, the application key and the application secret "
                    "must be set before validation."
                )  # BOSD chnge text, endpoint does not need to be set
            )
        client = transip.TransIP(
            # endpoint=self.endpoint,
            application_key=self.application_key,
            login=self.transip_login,
        )

        # Request RO, /me/bill* API access
        # ck = client.new_consumer_key_request() # BOSD disabled
        # ck.add_rules(transip.API_READ_ONLY, "/me/bill*")

        # Request validation
        # validation = ck.request()

        # if not validation["validationUrl"] or not validation["consumerKey"]:
        # raise UserError(_("The request to generate the consumer key failed."))

        # self.write(
        # {
        # "validation_url": validation["validationUrl"],
        # "consumer_key": validation["consumerKey"],
        # "state": "step3",
        # }
        # )
        # return self.action_continue_wizard()

    def run_step3(self):
        # self.ensure_one()
        # if not self.validation_url_ok:
        # raise UserError(
        # _(
        # "Go to the Validation URL, enter the required information and "
        # "validate, then check the option to attest that you did it."
        # )
        # )
        self.download_config_id.write(
            {
                # "transip_endpoint": self.endpoint,
                "transip_application_key": self.application_key.strip(),
                "transip_login": self.application_secret.strip(),
            }
        )
        return True
