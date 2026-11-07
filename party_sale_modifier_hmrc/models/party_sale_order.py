# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date
from odoo.exceptions import ValidationError, UserError
import calendar


class PartySaleOrder(models.Model):
    _inherit = 'sale.order'
    
    is_party_sale = fields.Boolean(string="Is Party", copy=False, default=False, index=True)
    name = fields.Char(string='Order Reference', copy=False, readonly=False, index=True, default=lambda self: 'New')
    broker_id = fields.Many2one('res.partner', string="Broker")
    broker_allotment_id = fields.Many2one('broker.allotment')
    freight_added = fields.Boolean(default=False)
    # product = fields.Char(compute="_compute_line_summary", string="Item")
    # qty = fields.Float(string="Party Qty")
    # brk_qty = fields.Float(string="Broker Qty")
    # bal_qty = fields.Float(string="Bal Qty")
    # rate = fields.Float(string="Party Rate")
    # broker_rate = fields.Float(string="B Rate", compute="_compute_rates")
    # tendor_rate = fields.Float(string="P Rate")
    # delivery = fields.Float(string="Delivery")
    product = fields.Char(compute="_compute_line_summary", store=True, string="Item")
    qty = fields.Float(compute="_compute_line_summary", store=True, string="Party Qty")
    rate = fields.Float(compute="_compute_line_summary", store=True, string="Party Rate")
    delivery = fields.Float(compute="_compute_delivery_total", store=True, string="Delivery")

    brk_qty = fields.Float(compute="_compute_rates", store=True, string="Broker Qty")
    bal_qty = fields.Float(compute="_compute_balance_qty", store=True, string="Bal Qty")
    broker_rate = fields.Float(compute="_compute_rates", store=True, string="B Rate")
    tendor_rate = fields.Float(compute="_compute_rates", store=True, string="P Rate")
    balance_qty = fields.Float(compute="_compute_balance_total", store=True, string="Bal Qty")

    tender_no = fields.Char(string="Tender No", compute="_compute_broker_details", store=True)
    vendor_id = fields.Many2one('res.partner', string="Vendor Name", compute="_compute_broker_details", store=True)
    item_id = fields.Many2one('product.product', string="Item", compute="_compute_broker_details", store=True)
    po_rate = fields.Float(string="PO Rate", compute="_compute_broker_details", store=True)
    brk_rate = fields.Float(string="BRK Rate", compute="_compute_broker_details", store=True)
    broker_no = fields.Char(string="Broker No", compute="_compute_broker_details", store=True)
    broker_id = fields.Many2one('res.partner', string="Broker Name", compute="_compute_broker_details", store=True)
    diff_rate = fields.Float(string="Diff Rate", compute="_compute_diff_rate", store=True)
    
    total_bal_amount = fields.Float(
        string="Balance Amt",
        compute="_compute_balance_amount",
        store=True,
        )
    credit_charge_type_id = fields.Many2one('overdue.charge', string="Credit Charges", store=True)
    def _compute_charge_line_count(self):
        for rec in self:
            rec.charge_line_count = len(rec.credit_charge_type_id.line_ids)
            
    def action_view_charge_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Delay Charges',
            'res_model': 'overdue.charge.line',
            'view_mode': 'list,form',
            'views': [(self.env.ref('party_sale_modifier_hmrc.view_overdue_charge_line_tree').id, 'list')],
            'domain': [('charge_id', '=', self.credit_charge_type_id.id)],
            'context': {'default_charge_id': self.credit_charge_type_id.id},
        }

        
    @api.depends('balance_qty', 'rate', 'order_line.tax_ids')
    def _compute_balance_amount(self):
        for rec in self:

            base_amount = (rec.balance_qty or 0) * (rec.rate or 0)
            tax_amount = 0
            for line in rec.order_line:
                if line.tax_ids:
                    taxes = line.tax_ids.compute_all(
                        line.price_unit,
                        currency=rec.currency_id,
                        quantity=rec.balance_qty,
                        product=line.product_template_id,
                        partner=rec.partner_id
                    )
                    tax_amount += taxes['total_included'] - taxes['total_excluded']
            rec.total_bal_amount = base_amount + tax_amount

    freight_rate = fields.Float(string="Freight Rate", store=True)

    @api.depends('order_line.price_unit', 'tender_id.order_line.price_unit', 'freight_rate')
    def _compute_diff_rate(self):
        for rec in self:
            sale_rate = rec.order_line[:1].price_unit if rec.order_line else 0
            po_rate = rec.tender_id.order_line[:1].price_unit if rec.tender_id and rec.tender_id.order_line else 0
            if rec.rate_type == 'for':
                rec.diff_rate = sale_rate - (po_rate + rec.freight_rate)
            else: 
                rec.diff_rate = sale_rate - po_rate

    def _default_voucher_date(self):
        today = fields.Date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]
        return date(today.year, today.month, last_day)

    voucher_date = fields.Date(string="Voucher Date", default=fields.Datetime.now)
    # def unlink(self):
    #     raise UserError(_("You are not allowed to delete Party records Because this is alloted by Broker"))

    @api.depends('tender_id')
    def _compute_broker_details(self):
        BrokerAllotment = self.env['broker.allotment']

        for so in self:
            so.tender_no = False
            so.vendor_id = False
            so.item_id = False
            so.po_rate = 0.0
            so.brk_rate = 0.0
            so.broker_no = False
            so.broker_id = False

            tender = so.tender_id
            if not tender:
                continue

            so.tender_no = tender.name

            so.vendor_id = tender.partner_id.id if tender.partner_id else False

            if tender.order_line:
                so.item_id = tender.order_line[0].product_id.id
                so.po_rate = tender.order_line[0].price_unit

            broker = BrokerAllotment.search(
                [('tender_id', '=', tender.id)],
                limit=1
            )
            if broker:
                so.broker_no = broker.name
                so.broker_id = broker.partner_id.id
                so.brk_rate = broker.total_rate

   

    @api.depends('order_line.qty_delivered')
    def _compute_delivery_total(self):
        for rec in self:
            delivered = 0
            for line in rec.order_line:
                delivered += line.qty_delivered or 0
            rec.delivery = delivered

    def action_confirm(self):
        for order in self:
            order._action_validate_receipt(order.qty)

            error_msg = order._confirmation_error_message()
            if error_msg:
                raise UserError(error_msg)

        self.order_line._validate_analytic_distribution()
        self.write(self._prepare_confirmation_values())
        context = self.env.context.copy()
        context.pop('default_name', None)
        context.pop('default_user_id', None)

        self.with_context(context)._action_confirm()
        self.filtered(lambda so: so._should_be_locked()).action_lock()

        if self.env.context.get('send_email'):
            self._send_order_confirmation_mail()

        return True
        
    def _action_confirm(self):
        result = super()._action_confirm()
        for order in self:
            if order.tender_id and order.tender_id.dispatch_location_id:
                order.picking_ids.write({
                    'location_id': order.tender_id.dispatch_location_id.id
                })
                order.picking_ids.move_ids.write({
                    'location_id': order.tender_id.dispatch_location_id.id
                })
        return result
    

    def _action_validate_receipt(self, qty):
        picking = self.tender_id.picking_ids.filtered(lambda p: p.state in ('assigned', 'confirmed') and p.picking_type_id.code == 'incoming')
        if not picking:
            return
        location_dest_id = self.tender_id.dispatch_location_id.id
        balance_qty = qty
        for move in picking.move_ids:
            move.location_dest_id = location_dest_id
            move.move_line_ids.unlink()
            if balance_qty <= 0:
                continue
            move_qty = min(move.product_uom_qty, balance_qty)
            self.env['stock.move.line'].create({
                'move_id': move.id,
                'product_id': move.product_id.id,
                'product_uom_id': move.product_uom.id,
                'qty_done': move_qty,
                'location_id': move.location_id.id,
                'location_dest_id': location_dest_id,
                'lot_name': self.tender_id.vendor_lot_no,
            })
            balance_qty -= move_qty
        picking.location_dest_id = location_dest_id
        picking.button_validate()
        picking._action_done()
        
    @api.depends(
        'order_line.product_uom_qty',
        'order_line.qty_delivered'
    )
    def _compute_balance_total(self):
        for rec in self:
            total_qty = 0
            total_delivered = 0

            if rec.order_line:
                for line in rec.order_line:
                    total_qty += line.product_uom_qty or 0
                    total_delivered += line.qty_delivered or 0

            rec.balance_qty = total_qty - total_delivered


    @api.depends(
        'order_line.product_uom_qty',
        'order_line.price_unit',
        # 'order_line.party_quantity',
        'order_line.product_id'
    )
    def _compute_line_summary(self):
        for rec in self:
            product = ''
            qty = 0
            rate = 0
            # prt_qty = 0

            if rec.order_line:
                for line in rec.order_line:
                    qty += line.product_uom_qty or 0
                    # prt_qty += line.party_quantity or 0

                product = rec.order_line[0].product_id.name or ''
                rate = rec.order_line[0].price_unit or 0

            rec.product = product
            rec.qty = qty
            rec.rate = rate
            # rec.prt_qty = prt_qty

    rate_type = fields.Selection([
        ('md', 'MD'),
        ('for', 'FOR'),
    ], string="Rate Type", default="")
    through = fields.Char(string="Through")

    lift_date = fields.Date(string="Lifting Date", default=_default_voucher_date)
    pay_date = fields.Date(string="Pay Date", default=_default_voucher_date)

    party_allotment_id = fields.Many2one(
        'purchase.order',
        string="Party Allotment",
        readonly=True
    )

    def action_create_party_order(self):
        self.ensure_one()

        vals = {
            'partner_id': self.party_id.id,
            'is_party_sale': True,
            'party_allotment_id': self.party_allotment_id.id,
            'lift_date': self.lift_date,
            'pay_date': self.pay_date,
        }

        sale_order = self.env['sale.order'].create(vals)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Party Order',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': sale_order.id,
            'target': 'current',
        }

    @api.depends('broker_allotment_id')
    def _compute_rates(self):
        for rec in self:
            rec.brk_qty = 0
            rec.bal_qty = 0
            rec.broker_rate = 0 
            rec.tendor_rate = 0
            if rec.broker_allotment_id:
                rec.brk_qty = rec.broker_allotment_id.total_qty
                rec.bal_qty = rec.broker_allotment_id.bal_qty
                rec.broker_rate = rec.broker_allotment_id.total_rate or 0
                rec.tendor_rate = rec.broker_allotment_id.tender_rate or 0
                
    # @api.depends('order_line')
    # def _compute_line_summary(self):
    #     for rec in self:
    #         if rec.order_line:
    #             rec.product = rec.order_line[0].product_id.name
    #             rec.qty = rec.order_line[0].product_uom_qty
    #             rec.rate = rec.order_line[0].price_unit
    #             rec.delivery = rec.order_line[0].qty_delivered
    #         else:
    #             rec.product = ''
    #             rec.qty = 0
    #             rec.rate = 0
    #             rec.delivery = 0
 
    @api.model_create_multi
    def create(self, vals_list):
        if 'is_party_sale' in vals_list[0] and vals_list[0]['is_party_sale'] == True:
            # vals['is_party_sale'] = True
            vals_list[0]['name'] = self.env['ir.sequence'].next_by_code('party.sale.order') or 'New'
        else:
            vals_list[0]['name'] = self.env['ir.sequence'].next_by_code('sale.order') or 'New'
        return super(PartySaleOrder, self).create(vals_list)

    # def action_add_freight(self):
    #     self.freight_added = True
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'freight.charge.line',
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': {'default_order_id': self.id}
    #     }



    is_immediate_payment = fields.Boolean(
        string="Is Immediate Payment",
        compute="_compute_is_immediate_payment",
        store=False
    ) 
    credit_charge_type_ids = fields.Many2one('overdue.charge', string="Credit Charges")

    @api.depends('payment_term_id')
    def _compute_is_immediate_payment(self):
        for order in self:
            if order.payment_term_id:
                order.is_immediate_payment = order.payment_term_id.name == 'Immediate Payment'
            else:
                order.is_immediate_payment = False


class ResPartner(models.Model):
    _inherit = 'res.partner'

    fassi_no = fields.Char(string="FSSAI No")
    credit_charge_type_id = fields.Many2one("overdue.charge", string="Credit Charge list")

    # credit_days = fields.Selection(
    #     [(str(i), str(i)) for i in range(0, 100)],
    #     string="Delay Days"
    # )

    # credit_days = fields.Integer(string="Credit Days")

    display_name = fields.Char(compute="_compute_display_name",store=True)

    @api.depends('name', 'city')
    def _compute_display_name(self):

        for partner in self:

            if partner.city:
                partner.display_name = f"{partner.name}, {partner.city}"
            else:
                partner.display_name = partner.name
