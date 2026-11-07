from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class PriceUpdateWhatsappWizard(models.TransientModel):
    _name = 'price.update.whatsapp.wizard'
    _description = 'Price Update WhatsApp Wizard'

    # Customers (already selected from action, UI me show nahi hoga)
    partner_ids = fields.Many2many(
        'res.partner',
        string="Customers",
        readonly=True
    )

    # Sirf message body
    notes = fields.Text(string="Message")

    def action_send_whatsapp(self):
        for partner in self.partner_ids:
            if not partner.phone:
                continue

            message = (
                f"Dear {partner.name},\n\n"
                f"{self.notes or ''}\n\n"
                f"– TG Sugar Team"
            )

            # Actual send
            # self.env['whatsapp.api'].send_message(
            #     partner.phone,
            #     message
            # )

            _logger.info("======= WHATSAPP MESSAGE PREVIEW =======")
            _logger.info("TO: %s", partner.phone)
            _logger.info("MESSAGE:\n%s", message)
            _logger.info("======================================")
