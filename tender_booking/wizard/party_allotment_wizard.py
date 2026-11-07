from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date, datetime
import logging
_logger = logging.getLogger(__name__)


class PartyAllotmentWizard(models.TransientModel):
    _name = "party.allotment.wizard"
    _description = "Party Allotment Wizard"

    tender_id = fields.Many2one('purchase.order', string="Tender")
    broker_allotment_id = fields.Many2one('broker.allotment')
    broker_id = fields.Many2one('res.partner', string="Party Name", domain=[
        ('is_broker_partner', '=', False), ('is_party_customer', '=', True)
    ])
    pay_date = fields.Date(string="Pay Date")
    lift_date = fields.Date(string="Lift Date")
    line_ids = fields.One2many('party.allotment.wizard.line', 'wizard_id', string="Item Details")

    sale_order_id = fields.Many2one('sale.order', string="Sale Order")

    # @api.constrains('pay_date', 'lift_date')
    # def _check_dates(self):
    #     for rec in self:
    #         if rec.lift_date <= rec.pay_date:
    #             raise ValidationError("Lift Date must be greater than Pay Date.")

    # @api.constrains('pay_date','lift_date', 'tender_id')
    # def _check_lift_date(self):
    #     for rec in self:
    #         if rec.pay_date and rec.lift_date and rec.tender_id.lift_date:
    #             tender_lift_date = rec.tender_id.lift_date
    #             tender_pay = rec.tender_id.pay_date
    #             if isinstance(tender_lift_date, datetime):
    #                 tender_lift_date = tender_lift_date.date()

    #             if isinstance(tender_pay, datetime):
    #               tender_pay = tender_pay.date()


    #             if rec.pay_date < tender_pay:
    #                 raise ValidationError(
    #                     "Pay Date cannot be LESS than Tender Pay Date (%s)." % tender_pay
    #                 )

    #             if rec.lift_date > tender_lift_date:
    #                 raise ValidationError(
    #                     "Lift Date cannot be greater than Tender Lift Date (%s)." 
    #                     % tender_lift_date
    #                 )

    @api.model
    def default_get(self, fields_list):
        res = super(PartyAllotmentWizard, self).default_get(fields_list)
        broker_allotment_id = self.env.context.get('active_id')
        res['broker_allotment_id'] = broker_allotment_id

        broker_allotment_id = self.env['broker.allotment'].browse(broker_allotment_id)
        tender_id = broker_allotment_id.tender_id.id
        if tender_id:
            tender = self.env['purchase.order'].browse(tender_id)
            res['tender_id'] = tender_id
            if tender.pay_date:
                res['pay_date'] = tender.pay_date.date() if isinstance(tender.pay_date, datetime) else tender.pay_date
            if tender.lift_date:
                res['lift_date'] = tender.lift_date.date() if isinstance(tender.lift_date, datetime) else tender.lift_date

            lines = []
            for line in broker_allotment_id.order_line.filtered(lambda l: l.balance_qty > 0):
                lines.append((0, 0, {
                    'broker_allotment_line_id': line.id,
                    'product_id': line.product_id.id,
                    'op_qty': line.product_uom_qty,
                    'balance_qty': line.balance_qty,
                    'current_allot_brk_qty': line.balance_qty,
                    'price_unit': line.price_unit,
                    'product_uom_id': line.product_uom_id.id,
                    'broker_price': line.price_unit,
                }))
            res['line_ids'] = lines
        return res

    # def _action_validate_receipt(self, qty):
    #     picking_id = self.tender_id.picking_ids.filtered(lambda l: l.state == 'assigned')
    #     qty_fields = 0
    #     balance_qty = qty
    #     location_dest_id = self.tender_id.dispatch_location_id.id
    #     for mv_id in picking_id.move_ids:
    #         mv_id.location_dest_id = location_dest_id
    #         if mv_id.quantity >= balance_qty and balance_qty > 0:
    #            mv_id.move_line_ids[0].location_dest_id = location_dest_id
    #            mv_id.move_line_ids[0].quantity = balance_qty
    #            mv_id.move_line_ids[0].lot_name = self.tender_id.vendor_lot_no
    #            balance_qty -= balance_qty
    #            for ml in mv_id.move_line_ids:
    #             if ml.id != mv_id.move_line_ids[0].id:
    #                 ml.unlink()
    #         elif mv_id.quantity < balance_qty and balance_qty > 0 and mv_id.quantity > 0:
    #            mv_id.move_line_ids[0].location_dest_id = location_dest_id
    #            mv_id.move_line_ids[0].quantity = mv_id.quantity
    #            mv_id.move_line_ids[0].lot_name = self.tender_id.vendor_lot_no
    #            balance_qty -= mv_id.quantity
    #            for ml in mv_id.move_line_ids:
    #             if ml.id != mv_id.move_line_ids[0].id:
    #                 ml.unlink()
    #         else:
    #            mv_id.move_line_ids[0].quantity = 0
    #     if picking_id:
    #         picking_id.location_dest_id = location_dest_id
    #         picking_id.button_validate()

    def action_create_allotment(self):
        has_valid_line = False
        lines_to_create = []
        
        for line in self.line_ids:
            if line.current_allot_brk_qty > 0:
                has_valid_line = True
                if not line.product_id:
                    continue
                available_qty = line.op_qty - line.alloted_brk_qty - line.alloted_party_qty
                if available_qty < 0:
                    available_qty = 0
                if line.current_allot_brk_qty > available_qty:
                    raise ValidationError(
                        f"Current Allot BRK Qty for '{line.product_id.display_name}' is {line.current_allot_brk_qty} but only {available_qty} is available.\n\n"
                        f"OP Qty: {line.op_qty}\n"
                        f"Already Alloted: {line.alloted_brk_qty + line.alloted_party_qty}\n"
                        f"Available: {available_qty}"
                    )
                lines_to_create.append(line)
        
        zero_price_line = self.line_ids.filtered(lambda l: l.broker_price == 0)
        if zero_price_line:
            raise ValidationError("Please enter Selling price greater than 0 in product \n" + str(zero_price_line.mapped('product_id.display_name')))
        if not has_valid_line:
            raise ValidationError("Please enter at least one item with Current Allot BRK Qty greater than 0.")
        
        sale = self.env['sale.order'].create({
            'is_party_sale': True,
            'partner_id': self.broker_id.id,
            'broker_id': self.broker_id.id,
            'party_tender_id': self.tender_id.id,
            'tender_id': self.tender_id.id,
            'pay_date': self.pay_date,
            'lift_date': self.lift_date,
            'broker_allotment_id': self.broker_allotment_id.id,
            'note': f"Party Allotment for Tender {self.tender_id.name}",
        })
        for line in lines_to_create:
            new_line = self.env['sale.order.line'].create({
                'order_id': sale.id,
                'broker_allotment_line_id': line.broker_allotment_line_id.id,
                'product_id': line.product_id.id,
                'name': line.product_id.display_name,
                'product_uom_qty': line.current_allot_brk_qty,
                'product_uom_id': line.product_uom_id.id,
                'price_unit': line.broker_price,
                'original_price': line.broker_price,
            })
            line.broker_allotment_line_id.party_qty += line.current_allot_brk_qty
            line.broker_allotment_line_id.balance_qty -= line.current_allot_brk_qty
            # Validate Receipt
            # self._action_validate_receipt(qty=line.current_allot_brk_qty)



            # ================= PARTY WHATSAPP MESSAGE =================
            party_number = self.broker_id.phone
            broker = self.broker_allotment_id.partner_id
            broker_number = broker.phone

            
            whatsapp_message = (
                f"The following items {line.product_id.display_name}, "
                f"Qty {line.current_allot_brk_qty} quintal "
                f"with defined price is booked."
            )


            _logger.warning("PARTY WHATSAPP MESSAGE READY AFTER PARTY ALLOTMENT")
            _logger.warning("Send To (Party): %s", self.broker_id.name)
            _logger.warning("Party Contact Number: %s", party_number)
            _logger.warning("Message: %s", whatsapp_message)
            _logger.warning("--------------------------------------------------")
            _logger.warning("Send To (Broker): %s", broker.name)
            _logger.warning("Broker Contact Number: %s", broker_number)
            _logger.warning("Message: %s", whatsapp_message)


            # ---------- REAL WHATSAPP INTEGRATION ----------
            template = self.env['whatsapp.template'].search(
                [('name', '=', 'party_allotment_msg')],
                limit=1
            )

            if template:

                # Party WhatsApp
                if party_partner and party_number:
                    party_msg = self.env['whatsapp.message'].create({
                        'template_id': template.id,
                        'partner_id': party_partner.id,
                        'model': self._name,
                        'res_id': self.id,
                        'values': {
                            'body_variables': [
                                line.product_id.display_name,
                                str(line.current_allot_brk_qty),
                            ]
                        }
                    })
                    party_msg.action_send()

                # Broker WhatsApp
                if broker_partner and broker_number:
                    broker_msg = self.env['whatsapp.message'].create({
                        'template_id': template.id,
                        'partner_id': broker_partner.id,
                        'model': self._name,
                        'res_id': self.id,
                        'values': {
                            'body_variables': [
                                line.product_id.display_name,
                                str(line.current_allot_brk_qty),
                            ]
                        }
                    })
                    broker_msg.action_send()

        broker_email = sale.partner_id.email
        group_admin = self.env.ref('tender_booking.group_master_admin')

        self.env.cr.execute("""
            SELECT uid FROM res_groups_users_rel WHERE gid = %s
        """, (group_admin.id,))

        admin_user_ids = [row[0] for row in self.env.cr.fetchall()]
        admin_users = self.env['res.users'].browse(admin_user_ids)

        admin_emails = admin_users.mapped('partner_id.email')
        admin_emails = [email for email in admin_emails if email]
        email_to = []

        if broker_email:
            email_to.append(broker_email)

        email_to.extend(admin_emails)

        if not email_to:
            return

        email_to = ",".join(set(email_to))  
        mail_values = {
            'subject': "Party Allotment Created",
            'body_html': """
                <p>Dear Sir,</p>
                <p>Party allotment has been successfully created.</p>
            """,
            'email_to': email_to,
        }
        self.env['mail.mail'].sudo().create(mail_values).send()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': sale.id,
            'view_mode': 'form',
            'target': 'current',
        }

class PartyAllotmentWizardLine(models.TransientModel):
    _name = "party.allotment.wizard.line"
    _description = "Party Allotment Wizard Line"

    wizard_id = fields.Many2one('party.allotment.wizard', string="Wizard")
    product_id = fields.Many2one('product.product', string="Item")
    op_qty = fields.Float(string="Order Qty", digits='Product Unit of Measure')
    broker_price = fields.Float(string="Party Price")
    balance_qty = fields.Float(string='Balance Qty')
    current_allot_brk_qty = fields.Float(string="Party Qty", digits='Product Unit of Measure')
    alloted_brk_qty = fields.Float(string="Alloted BRK Qty", digits='Product Unit of Measure')
    alloted_party_qty = fields.Float(string="Alloted Party Qty", digits='Product Unit of Measure')
    product_uom_id = fields.Many2one('uom.uom', string="UoM")
    broker_allotment_line_id = fields.Many2one('broker.allotment.line', string="Broker Allotment Line")
    price_unit = fields.Float(string="BRK Price")
    price_subtotal = fields.Float(string="Amt.")
    tax_ids = fields.Many2many('account.tax', string="Taxes")

    @api.onchange('current_allot_brk_qty')
    def _onchange_current_allot_brk_qty(self):
        available_qty = self.balance_qty
        # if available_qty < 0:
        #     available_qty = 0

        if self.current_allot_brk_qty and self.current_allot_brk_qty > self.balance_qty:
            val = self.current_allot_brk_qty
            self.current_allot_brk_qty = 0.0
            return {
                'warning': {
                    'title': 'Invalid Quantity',
                    'message': (
                        f"Current Allot BRK Qty ({val}) cannot exceed Available Qty ({available_qty}).\n\n"
                        f"OP Qty: {self.op_qty}\n"
                        f"Already Alloted: {self.alloted_brk_qty + self.alloted_party_qty}\n"
                        f"Available: {available_qty}"
                    )
                }
            }
