from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime
import calendar

class StockLocation(models.Model):
    _inherit = 'stock.location'
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        domain="[('supplier_rank', '>', 0)]"
    )

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    driver_id = fields.Many2one('res.partner', string='Driver')
    driver_phone = fields.Char('Driver Phone')
    vehicle_number = fields.Char('Vehicle Number')
    freight = fields.Float('Freight Rate')
    transport_id = fields.Many2one('res.partner', string='Transport')
    transport_name = fields.Many2one('transport.master', string='Transport')

    @api.onchange('driver_id')
    def _onchange_driver_id(self):
        self.driver_phone = self.driver_id.phone if self.driver_id else False

    @api.model
    def create(self, vals):
        picking = super().create(vals)
        if picking.picking_type_id.code == 'incoming':
            if picking.partner_id and picking.partner_id.received_location_id:
                picking.location_dest_id = picking.partner_id.received_location_id

        return picking

    @api.onchange('partner_id')
    def _onchange_partner_vendor_location(self):
        if self.picking_type_id.code == 'incoming':
            if self.partner_id and self.partner_id.received_location_id:
                self.location_dest_id = self.partner_id.received_location_id
            else:
                self.location_dest_id = self.picking_type_id.default_location_dest_id

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_party_customer = fields.Boolean(string="Is Party")

    received_location_id = fields.Many2one(
        'stock.location',
        string='Received Location',
        domain="[('usage', '=', 'internal')]"
    )

    @api.model_create_multi
    def create(self, vals_list):
        ctx = self.env.context

        for vals in vals_list:

            is_vendor_screen = ctx.get('default_supplier_rank') == 1
            is_broker = vals.get('is_broker_partner') or ctx.get('default_is_broker_partner')

            if is_broker:
                vals['customer_rank'] = 0
                vals['is_party_customer'] = False
                continue

            if is_vendor_screen:
                vals['supplier_rank'] = 1

                if not vals.get('is_party_customer'):
                    vals['customer_rank'] = 0
                    vals['is_party_customer'] = False

                else:
                    vals['customer_rank'] = 1
                    vals['is_party_customer'] = True

            else:
                vals['customer_rank'] = 1
                vals['is_party_customer'] = True

        partners = super().create(vals_list)

        for partner in partners:
            if partner.supplier_rank > 0 and not partner.received_location_id:
                location_name = partner.complete_name or 'New Vendor Location'

                parent_location = self.env['stock.location'].search([
                    ('complete_name', '=', 'WH/Stock'),
                    ('usage', '=', 'internal')
                ], limit=1)

                if not parent_location:
                    parent_location = self.env['stock.location'].search([
                        ('complete_name', '=', 'WH/Stock'),
                        ('usage', '=', 'internal')
                    ], limit=1)

                vendor_location = self.env['stock.location'].create({
                    'name': location_name,
                    'location_id': parent_location.id,
                    'usage': 'internal'
                })

                partner.received_location_id = vendor_location.id

        return partners

    def write(self, vals):
        res = super().write(vals)

        if vals.get('is_party_customer'):
            for rec in self:
                if rec.supplier_rank > 0:
                    rec.customer_rank = 1

        if 'name' in vals or 'parent_id' in vals:
            for rec in self:
                if rec.received_location_id:
                    rec.received_location_id.name = rec.complete_name

        return res

class PurchaseOrderLine(models.Model):
    _inherit = ['purchase.order.line', 'mail.thread']

    broker_quantity = fields.Float(string='Broker Qty.', copy=False)
    party_quantity = fields.Float(string='Party Qty.', copy=False, tracking=True, compute='_compute_party_quantity')
    current_price = fields.Float(string='Pr')
    balance_qty = fields.Float(string='Balance Qty.', compute='_compute_balance_qty',store="True")
    cus_packing_id = fields.Many2one('cus.product.package', string='Pack Type',  default=lambda self: self.env['cus.product.package'].search([('is_default','=',True)], limit=1))
    packing_qty = fields.Integer(string='Pack Qty.', tracking=True)
    pre_close_qty = fields.Float(string='Pre Close Qty', tracking=True)

    @api.depends('product_qty', 'broker_quantity')
    def _compute_balance_qty(self):
        for rec in self:
            # rec.balance_qty = rec.product_qty - (rec.broker_quantity + rec.party_quantity)
            rec.balance_qty = rec.product_qty - rec.broker_quantity

    @api.depends('order_id.broker_allotment_ids.order_line.party_qty', 'order_id.broker_allotment_ids.order_line.product_id', 'product_id')
    def _compute_party_quantity(self):
        for line in self:
            total_qty = 0.0
            for record in line.order_id.broker_allotment_ids:
                for rec in record.order_line:
                    if rec.product_id and rec.product_id == line.product_id:
                        total_qty += rec.party_qty or 0.0
            line.party_quantity = total_qty

    @api.onchange('cus_packing_id','packing_qty')
    def _onchange_set_qty(self):
        if self.cus_packing_id and self.packing_qty:
            self.product_qty = self.packing_qty * self.cus_packing_id.per_qt_quantity
        else:
            self.product_qty = 0
    
    @api.onchange('product_qty','cus_packing_id')
    def _onchange_set_pack_qty(self):
        if self.cus_packing_id and self.product_qty:
            self.packing_qty = self.product_qty / self.cus_packing_id.per_qt_quantity
        else:
            self.packing_qty = 0


    @api.onchange('product_qty')
    def _onchange_check_qty(self):
        if self.order_id.state == 'purchase' and self.product_qty < (self.broker_quantity):
            raise UserError('You cannot enter less than ' + str(self.broker_quantity) +  ' quantity as ' + str(self.broker_quantity)+ ' has already been allotted.')

    def write(self, vals):
        for rec in self:
            qty = rec.product_qty
            res = super().write(vals)
            if 'product_qty' in vals:
                new_qty = rec.product_qty

                # if new_qty < qty:
                #     raise UserError('After tender confirm system have not allow for decrease quantity. System allow only increase quantity.')
                #     picking_ids = rec.order_id.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
                #     for picking_id in picking_ids:
                #         picking_id.write({'location_id' : rec.order_id.dispatch_location_id.id}) 
                #         picking_id.move_ids.write({'location_id' : rec.order_id.dispatch_location_id.id}) 
                #         picking_id.move_line_ids.write({'location_id' : rec.order_id.dispatch_location_id.id}) 
                #         picking_id.button_validate()
                # if new_qty > qty:
                #     # picking_ids = rec.order_id.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
                #     # for picking_id in picking_ids:
                #     #     # picking_id.write({'location_id' : rec.order_id.dispatch_location_id.id}) 
                #     #     # picking_id.move_ids.write({'location_id' : rec.order_id.dispatch_location_id.id}) 
                #     #     # picking_id.move_line_ids.write({'location_id' : rec.order_id.dispatch_location_id.id}) 
                #     #     picking_id.button_validate()

                #     for picking in rec.order_id.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
                #         picking.action_assign()
                #         picking.location_dest_id = rec.order_id.dispatch_location_id.id
                #         for move in picking.move_ids:
                #             picking.location_dest_id = rec.order_id.dispatch_location_id.id
                #             for line in move.move_line_ids:
                #                 line.location_dest_id = rec.order_id.dispatch_location_id.id
                #                 if move.product_id.tracking in ('lot', 'serial') and not line.lot_id:

                #                     vendor_raw = rec.order_id.partner_id.name or ''
                #                     # vendor_clean = str(vendor_raw).strip()
                #                     # vendor_first = vendor_clean.split(' ')[0] if vendor_clean else 'Vendor'

                #                     booking_no = rec.order_id.booking_no or 'BK'

                #                     seq = self.env['ir.sequence'].next_by_code('vendor.lot.seq')
                #                     if not seq:
                #                         seq = '001'

                #                     lot_name = f"{vendor_raw}-{booking_no}-{seq}"

                #                     lot = self.env['stock.lot'].create({
                #                         'name': lot_name,
                #                         'product_id': move.product_id.id,
                #                         'company_id': rec.order_id.company_id.id,
                #                     })   
                #                     line.lot_id = lot.id
                #         # picking.button_validate()

            return res




    # billed_qty = fields.Float(
    #     string="Billed Qty",
    #     compute="_compute_billed_qty",
    #     store=True
    # )

    # @api.depends('order_id.invoice_ids.state',
    #              'order_id.invoice_ids.invoice_line_ids.quantity')
    # def _compute_billed_qty(self):
    #     for line in self:
    #         qty = 0.0
    #         bills = line.order_id.invoice_ids.filtered(lambda b: b.state == 'posted')
    #         for bill in bills:
    #             for inv_line in bill.invoice_line_ids:
    #                 if inv_line.product_id == line.product_id:
    #                     qty += inv_line.quantity
    #         line.billed_qty = qty


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    booking_no = fields.Char(
        string='Booking No',
        copy=False,
        tracking=True
    )
    def _default_voucher_date(self):
        today = fields.Date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]
        return date(today.year, today.month, last_day)

    booking_date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        tracking=True,
    )
    
    dispatch_location_id = fields.Many2one(
        'stock.location',
        string='Dispatch From',
        tracking=True,
        domain="[('usage', '=', 'supplier'), ('partner_id', '=', partner_id)]"
    )

    contract_no = fields.Char(
        string='Contract No',
        tracking=True
    )
    
    godown_type = fields.Selection([
        ('direct', 'Direct'),
        ('others', 'Others')
    ], string='Godown', default='direct', tracking=True)
    
    pay_date = fields.Datetime(
        string='Pay Date', default=_default_voucher_date, tracking=True
    )
    lift_date = fields.Datetime(
        string='Lifting Date', default=_default_voucher_date, tracking=True
    )

    is_tender_booking = fields.Boolean(
        string='Is Tender Booking',
        default=False,
        copy=False
    )

    voucher_date = fields.Date(string="Voucher Date", default=fields.Datetime.now)

    # product = fields.Char(compute="_compute_line_summary", string="Item")
    # qty = fields.Float(string="Tender Qty",)
    # brk_qty = fields.Float(string="Broker Qty")
    # prt_qty = fields.Float(string="Party Qty")
    # bal_qty = fields.Float(string="Balance Qty")
    # rate = fields.Float(string="Tender Rate")
    # delivery = fields.Float(string="Delivery", compute="_compute_delivery_total")


    product = fields.Char(compute="_compute_line_summary", store=True, string="Item")
    qty = fields.Float(compute="_compute_line_summary", store=True, string="Tender Qty")
    rate = fields.Float(compute="_compute_line_summary", store=True, string="Tender Rate")
    brk_qty = fields.Float(compute="_compute_line_summary", store=True, string="Broker Qty")
    brk_bal_qty = fields.Float(compute="_compute_line_summary", store=True, string="Brk Balance Qty")
    prt_qty = fields.Float(compute="_compute_line_summary", store=True, string="Party Qty")
    bill_qty = fields.Float(compute="_compute_line_summary", store=True, string="Billed Qty")
    del_bal_qty = fields.Float(compute="_compute_line_summary", store=True, string="Del Balance Qty")
    bal_qty = fields.Float(compute="_compute_line_summary", store=True, string="Balance Qty")
    delivery = fields.Float(string="Delivered", compute="_compute_delivery_total")
    invoice_qty = fields.Float(compute="_compute_delivery_total", string="Invoiced Qty")
    diff_rate = fields.Float(string="Diff Rate", compute="_compute_diff_rate", store=True)
    party_so_qty_bal = fields.Float(string="Party SO Qty Bal", compute="_compute_party_so_qty_bal",store=True)
    pre_close_qty = fields.Float(string='Pre Close Qty', compute="_compute_pre_close_qty")
    total_bal_amount = fields.Float(
        string="Balance Amt",
        compute="_compute_balance_amount",
        store=True,
    )
    def _compute_pre_close_qty(self):
        for rec in self:
            rec.pre_close_qty = 0.0  
            if rec.order_line:
                rec.pre_close_qty = rec.order_line[0].pre_close_qty

    def action_open_preclose_wizard(self):
        self.ensure_one()
        if not self.order_line:
            raise UserError("No lines found in Purchase Order")
        line = self.order_line[0]
        return {
            'name': 'Pre Close Qty',
            'type': 'ir.actions.act_window',
            'res_model': 'pre.close.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_line_id': line.id,
                'default_balance_qty': line.balance_qty,
            }
        }

    @api.depends('bal_qty', 'order_line.price_unit', 'order_line.tax_ids')
    def _compute_balance_amount(self):
        for line in self:

            base_amount = (line.bal_qty or 0) * (line.rate or 0)
            tax_amount = 0
            if line.order_line and line.order_line.tax_ids:
                taxes = line.order_line.tax_ids.compute_all(
                    line.rate,
                    currency=line.currency_id,
                    quantity=line.bal_qty,
                    product=line.product_id,
                    partner=line.partner_id
                )
                tax_amount = taxes['total_included'] - taxes['total_excluded']
            line.total_bal_amount = base_amount + tax_amount

    @api.depends('prt_qty', 'delivery')
    def _compute_party_so_qty_bal(self):
        for rec in self:
            rec.party_so_qty_bal = max((rec.prt_qty or 0.0) - (rec.delivery or 0.0), 0.0)
  
    @api.depends('order_line.product_id', 'order_line.product_qty', 'order_line.price_unit',
             'order_line.broker_quantity', 'order_line.party_quantity', 'order_line.balance_qty','order_line.qty_invoiced','delivery','invoice_qty')
    def _compute_line_summary(self):
        for rec in self:
            if rec.order_line:
                rec.product = rec.order_line[0].product_id.name
                rec.qty = rec.order_line[0].product_qty
                rec.rate = rec.order_line[0].price_unit
                rec.brk_qty = rec.order_line[0].broker_quantity
                rec.prt_qty = rec.order_line[0].party_quantity
                rec.bal_qty = rec.order_line[0].balance_qty
                rec.bill_qty = rec.order_line[0].qty_invoiced
                rec.brk_bal_qty = rec.brk_qty - rec.prt_qty
                # rec.del_bal_qty = (rec.delivery or 0.0) - (rec.bill_qty or 0.0)
                rec.del_bal_qty = max((rec.delivery or 0.0) - (rec.invoice_qty or 0.0), 0.0)
            else:
                rec.product = '' 
                rec.qty = 0
                rec.rate = 0

    @api.depends('order_line.price_unit')
    def _compute_diff_rate(self):
        pass
        # for rec in self:

        #     po_rate = rec.order_line[:1].price_unit if rec.order_line else 0

        #     so_rate = 0
        #     freight = 0

        #     sale = self.env['sale.order'].search([
        #         ('tender_id', '=', rec.id)
        #     ], limit=1)

        #     if sale and sale.order_line:
        #         so_rate = sale.order_line[:1].price_unit

        #     freight_rate = rec.sale.order_line.freight_rate or 0
        #     rec.diff_rate = so_rate - (po_rate + freight_rate)


    @api.depends('party_allotment_ids.order_line.qty_delivered','party_allotment_ids.order_line.qty_invoiced')
    def _compute_delivery_total(self):
        for rec in self:
            total = 0
            inv_total = 0
            for record in rec.party_allotment_ids:
                for line in record.order_line:
                    total += line.qty_delivered or 0
                    inv_total += line.qty_invoiced or 0
            rec.delivery = total
            rec.invoice_qty = inv_total

    broker_allotment_ids = fields.One2many('broker.allotment', 'tender_id', string='Broker Order')
    party_allotment_ids = fields.One2many('sale.order', 'tender_id', string='Party Order')
    broker_allotment_count = fields.Integer(string='Broker Orders', compute='_compute_sale')
    party_allotment_count = fields.Integer(string='Party Orders', compute='_compute_sale')
    vendor_lot_no = fields.Char(string='Vendor Lot Number')

    def _compute_lot_no(self):
        for order in self:
            vendor_raw = order.partner_id.name or ''
            booking_no = order.name or 'BK'
            # seq = self.env['ir.sequence'].next_by_code('vendor.lot.seq')
            # if not seq:
            #     seq = '001'
            order.vendor_lot_no = f"{vendor_raw}-{booking_no}"

    def button_confirm(self):
        res = super().button_confirm()

        for order in self:
            order._compute_lot_no()
                # for picking in order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
                #     picking.action_assign()
                #     picking.location_dest_id = order.dispatch_location_id.id
                #     for move in picking.move_ids:
                #         picking.location_dest_id = order.dispatch_location_id.id
                #         for line in move.move_line_ids:
                #             line.location_dest_id = order.dispatch_location_id.id
                #             if move.product_id.tracking in ('lot', 'serial') and not line.lot_id:

                #                 vendor_raw = order.partner_id.name or ''
                #                 # vendor_clean = str(vendor_raw).strip()
                #                 # vendor_first = vendor_clean.split(' ')[0] if vendor_clean else 'Vendor'

                #                 booking_no = order.booking_no or 'BK'

                #                 seq = self.env['ir.sequence'].next_by_code('vendor.lot.seq')
                #                 if not seq:
                #                     seq = '001'

                #                 lot_name = f"{vendor_raw}-{booking_no}-{seq}"

                #                 lot = self.env['stock.lot'].create({
                #                     'name': lot_name,
                #                     'product_id': move.product_id.id,
                #                     'company_id': order.company_id.id,
                #                 })   
                #                 line.lot_id = lot.id
                #     # picking.button_validate()
        return res

    @api.onchange('partner_id')
    def _onchange_partner_id_set_dispatch_location(self):
        if self.partner_id and self.partner_id.received_location_id:
            self.dispatch_location_id = self.partner_id.received_location_id
        else:
            self.dispatch_location_id = False
    
    def action_open_broker_wizard(self):
        return {
            'name': "Broker Allotment",
            'type': 'ir.actions.act_window',
            'res_model': 'broker.allotment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tender_id': self.id,
                'default_pay_date': self.pay_date,
                'default_lift_date': self.lift_date,
                'default_is_broker_partner': True, 
            }
        }

    def action_open_party_wizard(self):
        return {
            'name': "Party Allotment",
            'type': 'ir.actions.act_window',
            'res_model': 'party.allotment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tender_id': self.id,
                'default_pay_date': self.pay_date,
                'default_lift_date': self.lift_date,
                'default_is_broker_partner': False,
            }
        }

    @api.constrains('order_line')
    def _check_single_line_option(self):
        for order in self:
            if order.company_id.allow_multiple_line:
                continue
            product_lines = order.order_line.filtered(lambda l: l.product_id)
            if len(product_lines) > 1:
                raise ValidationError("Only one Item can be added in tender.")

    @api.constrains('booking_no')
    def _check_unique_booking_no(self):
        for rec in self:
            if rec.booking_no:
                existing = self.search([
                    ('booking_no', '=', rec.booking_no),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError("Booking No must be unique!")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                if self._context.get('is_tender_booking') or vals.get('is_tender_booking'):
                    vals['is_tender_booking'] = True
                    vals['name'] = self.env['ir.sequence'].next_by_code('tender.booking') or 'New'
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code('purchase.order') or 'New'
        return super(PurchaseOrder, self).create(vals_list)
    
    # @api.constrains('booking_date', 'pay_date', 'lift_date')
    # def _check_dates(self):
    #     for rec in self:
    #         if rec.pay_date and rec.booking_date and rec.pay_date <= rec.booking_date:
    #             raise ValidationError("Pay Date must be greater than Booking Date.")

    #         if rec.lift_date and rec.pay_date and rec.lift_date <= rec.pay_date:
    #             raise ValidationError("Lifting Date must be greater than Pay Date.")

    def _compute_sale(self):
        for rec in self:
            rec.broker_allotment_count = len(rec.broker_allotment_ids)
            rec.party_allotment_count = len(rec.party_allotment_ids)

    def open_broker_allotment(self):
        self.ensure_one()
        source_orders = self.broker_allotment_ids
        result = self.env['ir.actions.act_window']._for_xml_id('sale_order_modifier_hmrc.action_broker_allotment')
        if len(source_orders) > 1:
            result['context'] = {}
            result['domain'] = [('id', 'in', source_orders.ids)]
        elif len(source_orders) == 1:
            result['views'] = [(self.env.ref('sale_order_modifier_hmrc.view_broker_allotment_form', False).id, 'form')]
            result['res_id'] = source_orders.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result


    vendor_bill_created = fields.Boolean(
        string="Vendor Bill Created",
        compute="_compute_has_remaining_qty"
    )

    def _compute_has_remaining_qty(self):
        MoveLine = self.env['account.move.line']
        for order in self:

            remaining_qty = 0

            for line in order.order_line:

                total_qty = line.product_qty or 0
                broker_qty = line.broker_quantity or 0

                tender_allowed_qty = total_qty - broker_qty

                already_billed = sum(
                    MoveLine.search([
                        ('purchase_line_id','=', line.id),
                        ('move_id.move_type','=','in_invoice'),
                        ('move_id.state','!=','cancel'),
                        ('move_id.picking_id','=', False),
                    ]).mapped('quantity')
                )

                remaining = tender_allowed_qty - already_billed

                if remaining > 0:
                    remaining_qty += remaining

            order.vendor_bill_created = remaining_qty > 0

    def action_create_vendor_bill(self):
        self.ensure_one()

        MoveLine = self.env['account.move.line']

        invoice_lines = []

        for line in self.order_line:

            total_qty = line.product_qty or 0
            broker_qty = line.broker_quantity or 0

            tender_allowed_qty = total_qty - broker_qty

            already_billed = sum(
                MoveLine.search([
                    ('purchase_line_id','=', line.id),
                    ('move_id.move_type','=','in_invoice'),
                    ('move_id.state','!=','cancel'),
                    ('move_id.picking_id','=', False),
                ]).mapped('quantity')
            )

            remaining_qty = tender_allowed_qty - already_billed

            if remaining_qty <= 0:
                continue
            qty = remaining_qty

            expense_account = (
                line.product_id.property_account_expense_id
                or line.product_id.categ_id.property_account_expense_categ_id
            )

            invoice_lines.append((0,0,{
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': qty,
                'price_unit': line.price_unit,
                'account_id': expense_account.id,
                'purchase_line_id': line.id,
            }))

        if not invoice_lines:
            raise UserError(_("No balance quantity to bill."))

        bill = self.env['account.move'].create({
            'move_type':'in_invoice',
            'partner_id':self.partner_id.id,
            'invoice_origin':self.name,
            'invoice_date':fields.Date.context_today(self),
            'invoice_line_ids':invoice_lines,
            'auto_tds_apply': False,
        })
        bill.action_post()


        return {
            'type':'ir.actions.act_window',
            'res_model':'account.move',
            'res_id':bill.id,
            'view_mode':'form',
        }

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.constrains('quantity')
    def _check_purchase_line_balance(self):

        MoveLine = self.env['account.move.line']

        for line in self:

            if not line.purchase_line_id:
                continue

            po_line = line.purchase_line_id

            total_qty = po_line.product_qty or 0
            broker_qty = po_line.broker_quantity or 0

            total_already_billed = sum(
                MoveLine.search([
                    ('move_id', '!=', line.move_id.id),
                    ('purchase_line_id', '=', po_line.id),
                    ('move_id.move_type', '=', 'in_invoice'),
                    ('move_id.state', 'in', ['draft', 'posted']),
                    ('move_id.picking_id', '=', False),
                ]).mapped('quantity')
            )

            current_invoice_qty = sum(
                line.move_id.invoice_line_ids.filtered(
                    lambda l: l.purchase_line_id == po_line
                ).mapped('quantity')
            )

            if total_already_billed + current_invoice_qty > total_qty:
                raise UserError("Total billed quantity cannot exceed ordered quantity.")

            is_broker_invoice = bool(line.move_id.picking_id)

            if is_broker_invoice:
                allowed_qty = broker_qty

                already_posted = sum(
                    MoveLine.search([
                        ('move_id', '!=', line.move_id.id),
                        ('purchase_line_id', '=', po_line.id),
                        ('move_id.move_type', '=', 'in_invoice'),
                        ('move_id.state', 'in', ['draft', 'posted']),
                        ('move_id.picking_id', '!=', False),
                    ]).mapped('quantity')
                )

            else:
                allowed_qty = total_qty - broker_qty

                already_posted = sum(
                    MoveLine.search([
                        ('move_id', '!=', line.move_id.id),
                        ('purchase_line_id', '=', po_line.id),
                        ('move_id.move_type', '=', 'in_invoice'),
                        ('move_id.state', 'in', ['draft', 'posted']),
                        ('move_id.picking_id', '=', False),
                    ]).mapped('quantity')
                )

            if already_posted + current_invoice_qty > allowed_qty:
                raise UserError("Billing quantity cannot exceed allowed quantity.")

            if line.move_id.picking_id:

                pickings = line.move_id.picking_ids or line.move_id.picking_id

                if not pickings:
                    continue

                if isinstance(pickings, models.Model):
                    pickings = pickings

                delivered_qty = sum(
                    pickings.mapped('move_line_ids')
                    .filtered(lambda m: m.product_id == line.product_id)
                    .mapped('qty_done')
                )

                already_billed_do = sum(
                    MoveLine.search([
                        ('move_id', '!=', line.move_id.id),
                        ('product_id', '=', line.product_id.id),
                        ('purchase_line_id', '=', po_line.id),
                        ('move_id.move_type', '=', 'in_invoice'),
                        ('move_id.state', '=', 'posted'),
                        '|',
                        ('move_id.picking_id', 'in', pickings.ids),
                        ('move_id.picking_ids', 'in', pickings.ids),
                    ]).mapped('quantity')
                )

                current_invoice_qty = sum(
                    line.move_id.invoice_line_ids.filtered(
                        lambda l: l.product_id == line.product_id
                    ).mapped('quantity')
                )

                if already_billed_do + current_invoice_qty > delivered_qty:
                    raise UserError(
                        f"Vendor bill qty exceeded delivered qty.\n\n"
                        f"Delivered : {delivered_qty}\n"
                        f"Already billed : {already_billed_do}\n"
                        f"Current : {current_invoice_qty}\n"
                        f"Remaining : {delivered_qty - already_billed_do}"
                    )

    @api.constrains('quantity')
    def _check_do_invoice_qty(self):

        MoveLine = self.env['account.move.line']

        for line in self:
            if line.move_id.reversed_entry_id:
                continue
            if line.move_id.move_type in ['out_refund', 'in_refund']:
                continue
            # if line.move_id.move_type in ['out_refund', 'in_refund'] or line.move_id.reversed_entry_id:
            #     continue
            if line.move_id.move_type != 'out_invoice':
                continue
            if not line.move_id.picking_id:
                continue

            picking = line.move_id.picking_id
            delivered_qty = sum(
                picking.move_line_ids.filtered(
                    lambda m: m.product_id == line.product_id
                ).mapped('qty_done')
            )

            already_billed = sum(
                MoveLine.search([
                    ('id', '!=', line.id),
                    ('product_id', '=', line.product_id.id),
                    ('move_id.move_type', '=', 'out_invoice'),
                    ('move_id.picking_id', '=', picking.id),
                    ('move_id.state', '!=', 'cancel'),
                ]).mapped('quantity')
            )

            if already_billed + line.quantity > delivered_qty:

                raise ValidationError(
                    f"Invoice quantity exceeded!\n\n"
                    f"Delivered Qty : {delivered_qty}\n"
                    f"Already Invoiced : {already_billed}\n"
                    f"Allowed Remaining : {delivered_qty - already_billed}"
                )

class ResCompany(models.Model):
    _inherit = "res.company"

    allow_multiple_line = fields.Boolean(string="Allow Multiple Line in Tender")
    fssai_no = fields.Char(string="Fssai No")
    fax = fields.Char(string="Fax No")
