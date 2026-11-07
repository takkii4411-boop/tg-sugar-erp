# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date
from odoo.exceptions import ValidationError, UserError

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    original_price = fields.Float(string="Actual Price Unit", digits='Product Price', store=True, readonly=True)
    credit_days = fields.Integer(string="Credit Days")
    # delay_days = fields.Integer(string="Credit Days")
    delay_days = fields.Selection([(str(i), str(i)) for i in range(0, 100)], string="Credit Days")
    credit_charge = fields.Float(string="Credit Charge")
    delay_charge = fields.Float(string="Credit Charge")

    @api.onchange('delay_charge')
    def _onchange_delay_charge(self):
        for line in self:
            if line.original_price:
                line.price_unit = line.original_price + line.delay_charge

    @api.onchange('delay_days')
    def _onchange_delay_days(self):
        for line in self:
            order = line.order_id

            if not order or not order.credit_charge_type_ids:
                line.delay_charge = 0.0
                return

            if not line.original_price:
                line.original_price = line.price_unit or line.product_id.lst_price

            base_price = line.original_price

            charge_line = order.credit_charge_type_ids.line_ids.filtered(
                lambda l: l.delay_day == line.delay_days
            )

            if not charge_line:
                raise UserError(
                    f"Delay charge not configured for {line.delay_days} days "
                    f"in {order.credit_charge_type_ids.name}."
                )

            total_delay = charge_line[0].delay_charge
            line.delay_charge = total_delay
            line.price_unit = base_price + total_delay

    def apply_credit_charge(self):
        for line in self:
            order = line.order_id
            if not order or not order.credit_charge_type_ids:
                continue

            days = 0

            if not line.original_price:
                line.original_price = line.price_unit or line.product_id.lst_price

            base_price = line.original_price

            if not days:
                line.delay_charge = 0.0
                line.price_unit = base_price
                continue

            charge_line = order.credit_charge_type_ids.line_ids.filtered(
                lambda l: l.delay_day == days
            )

            if not charge_line:
                raise UserError(
                    f"Delay charge not configured for {days} days "
                    f"in {order.credit_charge_type_ids.name}."
                )

            total_delay = charge_line[0].delay_charge
            line.delay_charge = total_delay
            line.price_unit = base_price + total_delay

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.apply_credit_charge()
        return lines

    # @api.model_create_multi
    # def create(self, vals_list):
    #     lines = super().create(vals_list)
    #     for line in lines:
    #         base = getattr(line, "broker_price", 0.0) or line.price_unit or line.product_id.lst_price
    #         line.original_price = base
            
    #         line.apply_credit_charge()
            
    #     return lines


 
    # def apply_credit_charge(self):
    #     for line in self:
    #         if self.env.context.get("skip_credit_charge"):
    #             continue

    #         order = line.order_id
    #         if not order:
    #             continue

    #         term = order.payment_term_id
    #         # partner = order.partner_id

    #         days = 0
    #         if term:
    #             for term_line in term.line_ids:
    #                 days = max(days, term_line.nb_days or 0)

    #         line.credit_days = days

    #         if not days or days <= 0:
    #             line.credit_charge = 0.0

    #         if not line.original_price:
    #             base = getattr(line, "party_price", 0.0) or \
    #                    getattr(line, "broker_price", 0.0) or \
    #                    line.price_unit or line.product_id.lst_price
    #             line.original_price = base

    #         base_price = line.original_price
    #         auto_charge = 0.0

    #         if not (term and term.include_credit_charge and term.delay_days):
    #             line.with_context(skip_credit_charge=True).price_unit = base_price
    #             continue

    #         days = term.delay_days
    #         # qty = line.product_uom_qty

    #         # slabs = self.env['overdue.charge'].search([
    #         #     ('partner_id', '=', partner.id)
    #         # ], order="from_day asc")

    #         # if not slabs:
    #         #     slabs = self.env['overdue.charge'].search([
    #         #         ('partner_id', '=', False)
    #         #     ], order="from_day asc")

    #         # max_slab_day = max(slabs.mapped('to_day')) if slabs else 0
    #         # if days > max_slab_day:
    #         #     raise UserError(
    #         #         f"Credit days {days} is not configured for customer {partner.name}.\n"
    #         #         f"Maximum configured slab is {max_slab_day} days.\n"
    #         #         f"Please create an overdue charge slab up to {days} days first."
    #         #     )


    #         # DAY WISE
    #         charge = self.env['overdue.charge'].search([
    #             ('day', '=', days)
    #         ], limit=1) #order="day asc"


    #         if not charge:
    #             raise UserError(
    #                 f"Credit charge not configured for {days} days.\n"
    #                 f"Please create daywise credit charge first."
    #             )


    #         # if days not in configured_days:
    #         #     raise UserError(
    #         #         f"Credit charge not configured upto {days} days.\n"
    #         #         f"Please configure daywise credit charge first."
    #         #     )

    #         # total_delay = 0.0

    #         # for slab in slabs:
    #         #     if days < slab.from_day:
    #         #         continue

    #         #     slab_start = slab.from_day
    #         #     slab_end = slab.to_day

    #         #     applicable_days = min(days, slab_end) - slab_start + 1

    #         #     if applicable_days > 0:
    #         #         total_delay += applicable_days * slab.charge_per_quintal
    #         #         line.credit_charge = total_delay

    #         if line.delay_charge and line.delay_charge != auto_charge:
    #             line.with_context(skip_credit_charge=True).price_unit = base_price + line.credit_charge
    #             continue

    #         total_delay = charge.charge_per_quintal
    #         # total_delay = sum(charge.mapped('charge_per_quintal'))
    #         line.delay_charge = total_delay

    #         line.with_context(skip_credit_charge=True).price_unit = base_price + total_delay


    po_line_id = fields.Many2one('purchase.order.line', string="PO Line")
    party_po_line_id = fields.Many2one('broker.allotment.line', string="Broker Allotment Line")
    broker_allotment_line_id = fields.Many2one('broker.allotment.line', string="Broker Allotment Line")

    def write(self, vals):
        for rec in self:
            qty = rec.product_uom_qty
            res = super().write(vals)
            if 'product_uom_qty' in vals and rec.broker_allotment_line_id:
                new_qty = rec.product_uom_qty
                balance_qty = qty - new_qty
                if new_qty > qty + rec.broker_allotment_line_id.balance_qty:
                    raise ValidationError("You can not add more than balance Quantity.")
                rec.broker_allotment_line_id.party_qty -= balance_qty
                rec.broker_allotment_line_id.balance_qty += balance_qty
            return res

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    name = fields.Char(string='Order Reference', copy=False, readonly=True, index=True, default=lambda self: 'New')
    tender_id = fields.Many2one('purchase.order', string="Tender No")
    broker_tender_id = fields.Many2one('purchase.order', string="Tender No")
    party_tender_id = fields.Many2one('purchase.order', string="Party Tender No")
    note = fields.Text()
    pay = fields.Date(string="Pay Date")
    lift = fields.Date(string="Lift Date")
    broker_allotment_id = fields.Many2one('broker.allotment')

    def write(self, vals):
        for rec in self:
            res = super().write(vals)
            if 'state' in vals and rec.state == 'cancel':
                for line in rec.order_line.filtered(lambda l: l.broker_allotment_line_id or l.party_po_line_id):
                    balance_qty = line.product_uom_qty
                    if line.broker_allotment_line_id:
                        line.broker_allotment_line_id.party_qty -= balance_qty
                        line.broker_allotment_line_id.balance_qty += balance_qty

            # if not self.env.context.get('skip_credit_charge') and any(k in vals for k in ['payment_term_id', 'partner_id', 'order_line']):
            #     for order in self:
            #         order.order_line.apply_credit_charge()

            if 'delay_charge' in vals:
                if rec.original_price:
                    rec.price_unit = rec.original_price + rec.delay_charge

            elif any(k in vals for k in ['order_id', 'product_uom_qty']):
                rec.apply_credit_charge()
            return res

    def open_tender(self):
        self.ensure_one()
        source_orders = self.tender_id
        result = self.env['ir.actions.act_window']._for_xml_id('tender_booking.action_tender_booking')
        if len(source_orders) > 1:
            result['context'] = {}
            result['domain'] = [('id', 'in', source_orders.ids)]
        elif len(source_orders) == 1:
            result['views'] = [(self.env.ref('tender_booking.view_purchase_order_tender_form', False).id, 'form')]
            result['res_id'] = source_orders.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            if order.tender_id:
                for picking in order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
                    picking.write({'location_id' : order.tender_id.dispatch_location_id.id})
                    picking.move_ids.write({'location_id' : order.tender_id.dispatch_location_id.id})
                    picking.action_assign()
        return res

    @api.onchange('partner_id')
    def _onchange_partner_apply_credit(self):
        for order in self:
            if not order.partner_id:
                continue
            for line in order.order_line:
                line.apply_credit_charge()


    # @api.onchange('payment_term_id', 'partner_id')
    # def _onchange_payment_term_apply_charge(self):
    #     for order in self:
    #         for line in order.order_line:
    #             line.apply_credit_charge()


    # def write(self, vals):
    #     res = super().write(vals)

    #     for order in self:
    #         for line in order.order_line:
    #             line.apply_credit_charge()

    #     return res
