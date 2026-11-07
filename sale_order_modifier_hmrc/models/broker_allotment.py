# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date,datetime
import calendar
import logging
_logger = logging.getLogger(__name__)

class BrokerAllotment(models.Model):
    _name = 'broker.allotment'
    _description = 'Broker Allotment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_order desc, id desc' 

    name = fields.Char(string="Order Reference", required=True, copy=False, index='trigram', default=lambda self: _('New'))
    company_id = fields.Many2one(comodel_name='res.company', required=True, index=True, default=lambda self: self.env.company)
    partner_id = fields.Many2one(comodel_name='res.partner', string="Customer/Broker", required=True, change_default=True, index=True, tracking=1)
    state = fields.Selection(
        selection=[
            ('draft', "Draft"),
            ('confirm', "Confirm"),
            ('cancel', "Cancelled")], string="Status", readonly=True, copy=False, index=True, tracking=3, default='draft')

    date_order = fields.Datetime(
        string="Order Date",
        required=True, copy=False,
        default=fields.Datetime.now)

    note = fields.Html(
        string="Terms and conditions",
        store=True, readonly=False)
    order_line = fields.One2many(
        comodel_name='broker.allotment.line',
        inverse_name='broker_allotment_id',
        string="Order Lines",
        copy=True, bypass_search_access=True)

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        compute='_compute_currency_id',
        store=True,
        ondelete='restrict')
    

    def _default_voucher_date(self):
        today = fields.Date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]
        return date(today.year, today.month, last_day)

    voucher_date = fields.Date(string="Voucher Date", default=fields.Datetime.now)
    amount_untaxed = fields.Monetary(string="Untaxed Amount", store=True, compute='_compute_amounts', tracking=5)
    amount_tax = fields.Monetary(string="Taxes", store=True, compute='_compute_amounts')
    amount_total = fields.Monetary(string="Total", store=True, compute='_compute_amounts', tracking=4)

    tender_id = fields.Many2one('purchase.order', string="Tender No")
    pay = fields.Date(string="Pay Date", default=_default_voucher_date, tracking=True)
    lift = fields.Date(string="Lift Date", default=_default_voucher_date , tracking=True)

    party_allotment_ids = fields.One2many('sale.order', 'broker_allotment_id', string='Party Order')
    party_allotment_count = fields.Integer(string='Party Orders', compute='_compute_party_allotment')
 
    first_product = fields.Char(compute="_compute_line_summary", string="Item", store=True)
    prt_qty = fields.Float(string="Party Qty")
    total_qty = fields.Float(string="Brk Qty", compute="_compute_line_summary", store=True)
    bal_qty = fields.Float(string="Balance Qty", compute="_compute_balance_qty", store=True)
    total_rate = fields.Float(string="Brk Rate", compute="_compute_line_summary", store=True)
    po_rate = fields.Float(string="PO Rate", compute="_compute_line_summary", store=True)

    delivery = fields.Float(string="Delivery", compute="_compute_delivery_total")
    tender_rate = fields.Float(string="PO Rate", compute="_compute_tender_rate")
    vendor_id = fields.Many2one('res.partner',string='Vendor Name',related='tender_id.partner_id',store=True,readonly=True)
    diff_rate = fields.Float(string="Diff Rate",compute="_compute_diff_rate", store=True)

    balance_total = fields.Monetary(
        string="Bal Total",
        compute="_compute_balance_total",
        store=True,
        currency_field='currency_id'
    )
    # def unlink(self):
    #     raise UserError(_("You are not allowed to delete Broker records Because this is alloted by Tender"))

    @api.depends('order_line.balance_total')
    def _compute_balance_total(self):
        for rec in self:
            rec.balance_total = sum(
                rec.order_line.mapped('balance_total')
            )

    @api.depends('order_line.price_unit', 'tender_id.order_line.price_unit')
    def _compute_diff_rate(self):
        pass
        # for rec in self:

        #     so_rate = rec.order_line[:1].price_unit if rec.order_line else 0
        #     po_rate = rec.tender_id.order_line[:1].price_unit if rec.tender_id and rec.tender_id.order_line else 0
        #     freight_rate = rec.party_allotment_ids.freight_rate or 0
        #     rec.diff_rate = so_rate - (po_rate + freight_rate)

    @api.depends(
    'order_line.product_uom_qty',
    'order_line.party_qty'
    )
    def _compute_balance_qty(self):
        for rec in self:
            total_qty = 0
            party_qty = 0

            if rec.order_line:
                for line in rec.order_line:
                    total_qty += line.product_uom_qty or 0
                    party_qty += line.party_qty or 0

            rec.bal_qty = total_qty - party_qty


    @api.depends(
        'order_line.product_uom_qty',
        'order_line.party_qty',
        'order_line.price_unit',
        'order_line.product_id',
        'order_line.price_unit'
    )
    def _compute_line_summary(self):
        for rec in self:
            total_qty = 0
            party_qty = 0
            rate = 0
            product = ''
            price_unit=''

            if rec.order_line:
                for line in rec.order_line:
                    total_qty += line.product_uom_qty or 0
                    party_qty += line.party_qty or 0

                rate = rec.order_line[0].price_unit or 0
                product = rec.order_line[0].product_id.name or ''

            rec.total_qty = total_qty
            rec.prt_qty = party_qty
            rec.total_rate = rate
            rec.first_product = product


    @api.depends('tender_id.order_line.price_unit')
    def _compute_tender_rate(self):
        for rec in self:
            rate = 0
            if rec.tender_id and rec.tender_id.order_line:
                rate = rec.tender_id.order_line[0].price_unit or 0
            rec.tender_rate = rate

    @api.depends('party_allotment_ids.order_line.qty_delivered')
    def _compute_delivery_total(self):
        for rec in self:
            total = 0
            for record in rec.party_allotment_ids:
                for line in record.order_line:
                    total += line.qty_delivered or 0
            rec.delivery = total

    # @api.depends('order_line')
    # def _compute_line_summary(self):
    #     for rec in self:
    #         if rec.order_line:
    #             rec.first_product = rec.order_line[0].product_id.name
    #             rec.total_qty = rec.order_line[0].product_uom_qty
    #             rec.bal_qty = rec.order_line[0].balance_qty
    #             rec.prt_qty = rec.order_line[0].party_qty
    #             rec.total_rate = rec.order_line[0].price_unit
    #         else:
    #             rec.first_product = ''
    #             rec.total_qty = 0
    #             rec.bal_qty = 0
    #             rec.prt_qty = 0
    #             rec.total_rate = 0

    def open_party_allotment(self):
        self.ensure_one()
        source_orders = self.party_allotment_ids
        result = self.env['ir.actions.act_window']._for_xml_id('party_sale_modifier_hmrc.action_party_sale_order')
        if len(source_orders) > 1:
            result['context'] = {}
            result['domain'] = [('id', 'in', source_orders.ids)]
        elif len(source_orders) == 1:
            result['views'] = [(self.env.ref('sale.view_order_form', False).id, 'form')]
            result['res_id'] = source_orders.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    def _compute_party_allotment(self):
        for rec in self:
            rec.party_allotment_count = len(rec.party_allotment_ids)

    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total')
    def _compute_amounts(self):
        for record in self:
            record.amount_untaxed = sum(record.order_line.mapped('price_subtotal'))
            record.amount_tax = sum(record.order_line.mapped('price_tax'))
            record.amount_total = sum(record.order_line.mapped('price_total'))
            # record.tax_totals = record.amount_total

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

    @api.depends('company_id')
    def _compute_currency_id(self):
        for order in self:
            order.currency_id = order.company_id.currency_id

    @api.depends('partner_id')
    def _compute_display_name(self):
        for order in self:
            name = order.name
            if order.partner_id.name:
                name = f'{name} - {order.partner_id.name}'
            order.display_name = name

    # def _action_validate_receipt(self, qty):
    #     picking = self.tender_id.picking_ids.filtered(lambda p: p.state in ('assigned', 'confirmed'))
    #     if not picking:
    #         return
    #     location_dest_id = self.tender_id.dispatch_location_id.id
    #     balance_qty = qty
    #     for move in picking.move_ids:
    #         move.location_dest_id = location_dest_id
    #         move.move_line_ids.unlink()
    #         if balance_qty <= 0:
    #             continue
    #         move_qty = min(move.product_uom_qty, balance_qty)
    #         self.env['stock.move.line'].create({
    #             'move_id': move.id,
    #             'product_id': move.product_id.id,
    #             'product_uom_id': move.product_uom.id,
    #             'qty_done': move_qty,
    #             'location_id': move.location_id.id,
    #             'location_dest_id': location_dest_id,
    #             'lot_name': self.tender_id.vendor_lot_no,
    #         })
    #         balance_qty -= move_qty
    #     picking.location_dest_id = location_dest_id
    #     picking.button_validate()
    #     picking._action_done()

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    # def action_confirm(self):
    #     for rec in self:
    #         rec.state = 'confirm'
    def action_confirm(self):
        for rec in self:
            if rec.total_qty <= 0:
                raise ValidationError("Confirm qty must be greater than 0")
            # rec._action_validate_receipt(rec.total_qty)
            rec.state = 'confirm'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('broker.allotment') or 'New'
        return super(BrokerAllotment, self).create(vals_list)

    def action_open_party_wizard(self):
        return {
            'name': "Party Allotment",
            'type': 'ir.actions.act_window',
            'res_model': 'party.allotment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tender_id': self.tender_id.id,
                'default_pay_date': self.pay,
                'default_lift_date': self.lift}}

    def write(self, vals):
        for rec in self:
            res = super().write(vals)
            if 'state' in vals and rec.state == 'cancel':
                for line in rec.order_line.filtered(lambda l: l.po_line_id):
                    balance_qty = line.product_uom_qty
                    if line.po_line_id:
                        line.po_line_id.broker_quantity -= balance_qty
            return res

    def action_open_release_qty_wizard(self):
        self.ensure_one()
        return {
            'name': 'Release Quantity',
            'type': 'ir.actions.act_window',
            'res_model': 'broker.release.qty.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_broker_allotment_id': self.id,
                'default_broker_line_id': self.order_line[:1].id
            }
        }


class BrokerAllotmentLine(models.Model):
    _name = 'broker.allotment.line'
    _description = 'Broker Allotment Line'
    _rec_names_search = ['name', 'broker_allotment_id.name']
    _order = 'broker_allotment_id, sequence, id'

    broker_allotment_id = fields.Many2one('broker.allotment')
    sequence = fields.Integer(string="Sequence", default=10)
    po_line_id = fields.Many2one('purchase.order.line', string="PO Line")

    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Product",
        change_default=True, ondelete='restrict', index='btree_not_null')
    product_template_id = fields.Many2one(
        string="Product Template",
        comodel_name='product.template')

    product_uom_qty = fields.Float(
        string="Quantity",
        compute='_compute_product_uom_qty',
        digits='Product Unit', default=1.0,
        store=True, readonly=False, required=True)

    original_qty = fields.Float(string="Original Quantity", readonly=True)
    balance_qty = fields.Float(string='Balance Qty')
    party_qty = fields.Float(string='Party Qty')
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string="Unit",
        domain='[("id", "in", allowed_uom_ids)]',
        store=True, readonly=False, ondelete='restrict')

    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        string="Taxes",
        store=True, readonly=False)

    qty_delivered = fields.Float(
        string="Delivery Quantity",
        default=0.0,
        digits='Product Unit',
        store=True, readonly=False, copy=False)

    price_unit = fields.Float(
        string="Unit Price",
        digits='Product Price',
        store=True, readonly=False, required=True)

    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute='_compute_amount',
        store=True)
    price_tax = fields.Float(
        string="Total Tax",
        compute='_compute_amount',
        store=True)
    price_total = fields.Monetary(
        string="Total",
        compute='_compute_amount',
        store=True)

    currency_id = fields.Many2one(
        related='broker_allotment_id.currency_id',
        depends=['broker_allotment_id.currency_id'],
        store=True)

    
    balance_total = fields.Monetary(
        string="Bal Total",
        compute="_compute_balance_total",
        store=True,
        currency_field='currency_id'
    )

    @api.depends('balance_qty', 'price_unit', 'tax_ids')
    def _compute_balance_total(self):
        for line in self:
            # Base Amount = Balance Qty × Rate
            base_amount = (line.balance_qty or 0.0) * (line.price_unit or 0.0)
            total_amount = base_amount

            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    base_amount,
                    currency=line.currency_id,
                    quantity=1.0,
                    product=line.product_id,
                    partner=line.broker_allotment_id.partner_id
                )
                total_amount = taxes_res.get('total_included', base_amount)

            line.balance_total = round(total_amount)


    @api.depends('product_uom_qty', 'price_unit', 'tax_ids')
    def _compute_amount(self):
        for line in self:
            subtotal = line.product_uom_qty * line.price_unit
            taxes = line.tax_ids.compute_all(
                line.price_unit,
                currency=line.currency_id,
                quantity=line.product_uom_qty)
            line.price_subtotal = taxes.get('total_excluded', subtotal)
            line.price_tax = taxes.get('total_included', subtotal) - line.price_subtotal
            line.price_total = taxes.get('total_included', subtotal)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.original_qty = rec.product_uom_qty
        return records

    @api.constrains('product_uom_qty')
    def _check_qty_reduction_only(self):
        for line in self:
            if line.product_uom_qty > line.original_qty + line.po_line_id.balance_qty:
                raise ValidationError("You can not add more then balance Quantity.")

    def write(self, vals):
        for rec in self:
            qty = rec.product_uom_qty
            res = super().write(vals)
            if 'product_uom_qty' in vals and (rec.po_line_id):
                new_qty = rec.product_uom_qty
                balance_qty = qty - new_qty
                if new_qty > qty:
                    rec.original_qty = new_qty
                if rec.po_line_id:
                    rec.po_line_id.broker_quantity -= balance_qty
                    rec.balance_qty = new_qty
            return res

class L10nInWithholdWizard(models.TransientModel):
    _inherit = 'l10n_in.withhold.wizard'

    auto_select_section = fields.Boolean(string="Auto Select Section")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')

        if active_model == 'account.move' and active_id:
            invoice = self.env['account.move'].browse(active_id)
            if invoice:
                res['base'] = invoice.amount_untaxed
                res['default_base_amount'] = invoice.amount_untaxed

        return res

    default_base_amount = fields.Float(string="Default Base", readonly=True)

    @api.onchange('auto_select_section')
    def _onchange_auto_select_section(self):
        for rec in self:
            if rec.auto_select_section:
                tax_model = rec._fields['tax_id'].comodel_name
                tax = self.env[tax_model].search([('name', 'ilike', '194Q')], limit=1)

                if tax:
                    rec.tax_id = tax.id
                else:
                    rec.tax_id = False
            else:
                rec.tax_id = False

            if rec.default_base_amount:
                rec.base = rec.default_base_amount

    @api.onchange('tax_id')
    def _onchange_tax_id_keep_base(self):
        for rec in self:
            if rec.default_base_amount:
                rec.base = rec.default_base_amount
    
    @api.depends('tax_id', 'base')
    def _compute_amount(self):
        super()._compute_amount()
        for rec in self:
            if rec.amount:
                rec.amount = round(rec.amount)