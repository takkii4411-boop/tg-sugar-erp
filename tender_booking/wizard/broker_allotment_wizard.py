from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date, datetime
import logging
_logger = logging.getLogger(__name__)

class BrokerAllotmentWizard(models.TransientModel):
    _name = "broker.allotment.wizard"
    _description = "Broker Allotment Wizard"

    tender_id = fields.Many2one('purchase.order', string="Tender")
    broker_id = fields.Many2one('res.partner', string="Broker", domain="[('is_broker_partner', '=', True)]")
    pay_date = fields.Date(string="Pay Date")
    lift_date = fields.Date(string="Lift Date")
    line_ids = fields.One2many('broker.allotment.wizard.line', 'wizard_id', string="Item Details")

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
        res = super(BrokerAllotmentWizard, self).default_get(fields_list)
        active_id = self._context.get('active_id')
        if active_id:
            tender = self.env['purchase.order'].browse(active_id)
            res['tender_id'] = active_id
            if tender.pay_date:
                res['pay_date'] = tender.pay_date.date() if isinstance(tender.pay_date, datetime) else tender.pay_date
            if tender.lift_date:
                res['lift_date'] = tender.lift_date.date() if isinstance(tender.lift_date, datetime) else tender.lift_date
            
            lines = []
            for order_line in tender.order_line.filtered(lambda l: l.balance_qty > 0):
                # sale_order_lines = self.env['sale.order.line'].search([
                #     ('order_id.tender_id', '=', tender.id),
                #     ('order_id.is_broker_sale', '=', True),
                #     ('product_id', '=', order_line.product_id.id),
                #     ('order_id.state', '!=', 'cancel')
                # ])
                # alloted_qty = sum(sale_order_lines.mapped('product_uom_qty'))
                lines.append((0, 0, {
                    'order_line_id': order_line.id,
                    'product_id': order_line.product_id.id,
                    'op_qty': order_line.product_qty,
                    'balance_qty': order_line.balance_qty,
                    'current_allot_brk_qty': order_line.balance_qty,
                    'alloted_brk_qty': order_line.broker_quantity,
                    'alloted_brk_price': order_line.current_price,
                    'product_uom_id': order_line.product_uom_id.id,
                    'price_unit': order_line.price_unit,
                    'price_subtotal': order_line.price_subtotal,
                    'tax_ids': order_line.tax_ids.ids,
                    'broker_price': order_line.price_unit,
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
    #            mv_id.move_line_ids[0].qty_done = balance_qty
    #            mv_id.move_line_ids[0].lot_name = self.tender_id.vendor_lot_no
    #            balance_qty -= balance_qty
    #            for ml in mv_id.move_line_ids:
    #             if ml.id != mv_id.move_line_ids[0].id:
    #                 ml.unlink()
    #         elif mv_id.quantity < balance_qty and balance_qty > 0 and mv_id.quantity > 0:
    #            mv_id.move_line_ids[0].location_dest_id = location_dest_id
    #            # mv_id.move_line_ids[0].quantity = mv_id.quantity
    #            mv_id.move_line_ids[0].qty_done = mv_id.quantity
    #            mv_id.move_line_ids[0].lot_name = self.tender_id.vendor_lot_no
    #            balance_qty -= mv_id.quantity
    #            for ml in mv_id.move_line_ids:
    #             if ml.id != mv_id.move_line_ids[0].id:
    #                 ml.unlink()
    #         else:
    #            mv_id.move_line_ids[0].qty_done = 0 
    #     if picking_id:
    #         picking_id.location_dest_id = location_dest_id
    #         picking_id._action_done()



        # move_line = picking_id.move_line_ids
        # if move_line:
        #     move_line[0].lot_name = self.tender_id.vendor_lot_no
        #     move_line[0].quantity = qty
        #     picking_id.button_validate()

    def action_create_allotment(self): 
        has_valid_line = False
        lines_to_create = []        
        zero_price_line = self.line_ids.filtered(lambda l: l.broker_price == 0)
        if zero_price_line:
            raise ValidationError("Please enter Selling price greater than 0 in product \n" + str(zero_price_line.mapped('product_id.display_name')))
        if not self.line_ids.filtered(lambda l: l.current_allot_brk_qty > 0):
            raise ValidationError("Please enter at least one item with Current Allot BRK Qty greater than 0.")
        
        sale = self.env['broker.allotment'].create({
            'partner_id': self.broker_id.id,
            # 'broker_tender_id': self.tender_id.id,
            'tender_id': self.tender_id.id,
            'pay': self.pay_date,
            'lift': self.lift_date,
            'note': f"Broker Allotment for Tender {self.tender_id.name}",
        })
        lines_to_create = self.tender_id.order_line
        
        for line in self.line_ids.filtered(lambda l: l.current_allot_brk_qty > 0):
            self.env['broker.allotment.line'].create({
                'broker_allotment_id': sale.id,
                'po_line_id': line.order_line_id.id,
                'product_id': line.product_id.id,
                'product_template_id': line.product_id.product_tmpl_id.id,
                'product_uom_qty': line.current_allot_brk_qty,
                'original_qty': line.current_allot_brk_qty,
                'balance_qty': line.current_allot_brk_qty,
                'product_uom_id': line.product_uom_id.id,
                'price_unit': line.broker_price,
                'tax_ids': [(6, 0, line.product_id.taxes_id.ids)],
                'price_subtotal': line.price_subtotal,
            })
            line.order_line_id.broker_quantity += line.current_allot_brk_qty
            # line.order_line_id.current_price += line.broker_price

            # Validate Receipt
            # self._action_validate_receipt(qty=line.current_allot_brk_qty)



            # ================= WHATSAPP MESSAGE FORMAT =================
            broker_number = self.broker_id.phone

            whatsapp_message = (
                f"The following items {line.product_id.display_name}, "
                f"Qty {line.current_allot_brk_qty} quintal "
                f"with defined price allotted."
                f"Lifting Date: {self.lift_date}"
            )

            _logger.warning("=====WHATSAPP MESSAGE READY AFTER BROKER ALLOTMENT====")
            _logger.warning("Send To (Broker): %s", self.broker_id.name)
            _logger.warning("Broker Contact Number: %s", broker_number)
            _logger.warning("Message: %s", whatsapp_message)
            _logger.warning("--------------------------------------------------")


            # ================= REAL WHATSAPP SEND =================
            template = self.env['whatsapp.template'].search(
                [('name', '=', 'broker_allotment_msg')],
                limit=1
            )

            if template and broker_number:
                message = self.env['whatsapp.message'].create({
                    'template_id': template.id,
                    'partner_id': self.broker_id.id,
                    'model': self._name,
                    'res_id': self.id,
                    'values': {
                        'body_variables': [
                            line.product_id.display_name,
                            str(line.current_allot_brk_qty),
                            str(self.lift_date or ''),
                        ]
                    }
                })
                message.action_send()


        broker_email = sale.partner_id.email
        print("\n\n broker_email________",broker_email)

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
        print("\n\n broker_email________",broker_email)


        email_to.extend(admin_emails)

        if not email_to:
            return

        email_to = ",".join(set(email_to))  
        mail_values = {
            'subject': "Broker Allotment Created",
            'body_html': """
                <p>Dear Sir,</p>
                <p>Broker allotment has been successfully created.</p>
            """,
            'email_to': email_to,
        }
        print("\n\n emails_to________",email_to)


        self.env['mail.mail'].sudo().create(mail_values).send()
        print("\n\n emails________",mail_values)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'broker.allotment',
            'res_id': sale.id,
            'view_mode': 'form',
            'target': 'current',
        }


class BrokerAllotmentWizardLine(models.TransientModel):
    _name = "broker.allotment.wizard.line"
    _description = "Broker Allotment Wizard Line"
 
    wizard_id = fields.Many2one('broker.allotment.wizard', string="Wizard")
    product_id = fields.Many2one('product.product', string="Item")
    op_qty = fields.Float(string="Order Qty.", digits='Product Unit of Measure')
    alloted_brk_qty = fields.Float(string="Alloted BRK Qty", digits='Product Unit of Measure')
    alloted_brk_price = fields.Float(string="Rate", digits='Product Unit of Measure')
    current_allot_brk_qty = fields.Float(string="Selling Qty", digits='Product Unit of Measure')
    balance_qty = fields.Float(string='Balance Qty.')

    product_uom_id = fields.Many2one('uom.uom', string="UoM")
    order_line_id = fields.Many2one('purchase.order.line', string="Order Line")
    price_unit = fields.Float(string="PO Price")
    broker_price = fields.Float(string="Selling Price")
    price_subtotal = fields.Float(string="Amt.")
    tax_ids = fields.Many2many('account.tax', string="Taxes")

    @api.onchange('product_id')
    def _onchange_product_id_set_taxes(self):
        for rec in self:
            if rec.product_id:
                rec.tax_ids = rec.product_id.taxes_id
            else:
                rec.tax_ids = False
                
    @api.onchange('current_allot_brk_qty')
    def _onchange_current_allot_brk_qty(self):
        available_qty = self.balance_qty
        available_price = self.price_unit - self.alloted_brk_price
        if self.current_allot_brk_qty > self.balance_qty:
            val = self.current_allot_brk_qty
            self.current_allot_brk_qty = 0.0
            return {
                'warning': {
                    'title': 'Invalid Quantity',
                    'message': (
                        f"Current Allot BRK Qty ({val}) cannot exceed Available Qty ({self.balance_qty}).\n\n"
                        f"OP Qty: {self.op_qty}\n"
                        f"Already Alloted: {self.alloted_brk_qty}\n"
                        f"Available: {self.balance_qty}"
                    )
                }
            }
        # if self.broker_price > available_price:
        #     val = self.broker_price
        #     self.broker_price = 0.0
        #     return {
        #         'warning': {
        #             'title': 'Invalid Rate',
        #             'message': (
        #                 f"Current Allot BRK Rate ({val}) cannot exceed Available Rate ({available_price}).\n\n"
        #                 f"OP Rate: {self.price_unit}\n"
        #                 f"Already Alloted: {self.alloted_brk_price}\n"
        #                 f"Available: {available_price}"
        #             )
        #         }
        #     }
