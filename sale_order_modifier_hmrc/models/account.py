from odoo import models, fields, api
from datetime import date

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def tg_sugar_send_overdue_invoice_reminder(self):
        today = date.today()

        overdue_invoices = self.search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date_due', '<', today),
            ('payment_state', '!=', 'paid')
        ])
        print("Total overdue invoices found:", len(overdue_invoices))

        admin_user = self.env.ref('base.user_admin')

        for invoice in overdue_invoices:
            print("Processing Invoice:", invoice.name, invoice.partner_id.name)

            if invoice.partner_id.email: 
                print("Sending mail to Customer:", invoice.partner_id.email)

                template = self.env.ref('sale_order_modifier_hmrc.email_template_invoice_overdue')
                template.send_mail(invoice.id, force_send=True)
                print("Customer mail sent for invoice:", invoice.name)
            else:
                print("customer has no email configured")

            if admin_user.email:
                print("Sending mail to Admin:", admin_user.email)

                admin_template = self.env.ref('sale_order_modifier_hmrc.email_template_admin_overdue')
                admin_template.send_mail(invoice.id, force_send=True)
                print("Admin mail sent for invoice:", invoice.name)
            else:
                print("Admin has no email configured")