# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from datetime import date
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    vehicle_number = fields.Char(string='Vehicle Number',readonly=True)
    driver_name = fields.Char(string='Driver Name',readonly=True)
    driver_number = fields.Char(string='Driver Number',readonly=True)
    transport_name = fields.Char(string='Transport Name',readonly=True)
    invoice_date = fields.Date(readonly=False)
    picking_ids = fields.Many2many('stock.picking', string="Delivery Orders")
    auto_tds_apply = fields.Boolean(string="Auto TDS Apply", default=True)
    customer_id = fields.Many2one('res.partner', string="Delivery Address")

    broker_name = fields.Char(string="Broker", compute="_compute_custom_data", store=True)
    broker_rate = fields.Float(string="Broker Rate", compute="_compute_custom_data", store=True)
    total_qty = fields.Float(string="Qty", compute="_compute_custom_data", store=True)
    avg_rate = fields.Float(string="Rate", compute="_compute_custom_data", store=True)
    invoice_no_custom = fields.Char(string="Invoice No", compute="_compute_custom_data", store=False)
    invoice_date_custom = fields.Date(string="Invoiced Date", compute="_compute_custom_data", store=False)
    customer_name = fields.Char(string="Customer", compute="_compute_custom_data", store=True)
    so_rate = fields.Float(string="SO Rate", compute="_compute_custom_data", store=True)
    diff = fields.Float(string="Diff", compute="_compute_custom_data", store=True)
    d_amt = fields.Float(string="D Amt", compute="_compute_custom_data", store=True)
    do_number = fields.Many2one('stock.picking', string="DO Number", related='picking_id', readonly=True)

    @api.depends('invoice_line_ids', 'invoice_origin', 'partner_id', 'invoice_date')
    def _compute_custom_data(self):
        for rec in self:

            rec.broker_name = ''
            rec.broker_rate = 0.0
            rec.total_qty = 0.0
            rec.avg_rate = 0.0
            rec.customer_name = f"{rec.partner_id.name}, {rec.partner_id.city or ''}"
            rec.so_rate = 0.0
            rec.diff = 0.0
            rec.d_amt = 0.0

            sale = self.env['sale.order'].search([
                ('name', '=', rec.invoice_origin)
            ], limit=1)

            invoice = False

            if sale:
                picking = sale.picking_ids.filtered(lambda p: p.state == 'done')[:1]
                if picking and picking.customer_invoice_id:
                    invoice = picking.customer_invoice_id

            rec.invoice_no_custom = invoice.name if invoice else ''
            rec.invoice_date_custom = invoice.invoice_date if invoice else False

            if not sale:
                continue

            rec.broker_name = sale.broker_id.name if sale.broker_id else ''
            rec.broker_rate = getattr(sale, 'broker_rate', 0.0)
            picking = sale.picking_ids.filtered(lambda p: p.state == 'done')[:1]
          
            if sale.order_line:
                rec.so_rate = sale.order_line[0].price_unit or 0.0

            total_qty = sum(rec.invoice_line_ids.mapped('quantity'))
            rec.total_qty = total_qty

            total_amount = sum(rec.invoice_line_ids.mapped('price_subtotal'))

            purchase_rate = (total_amount / total_qty) if total_qty else 0.0
            rec.avg_rate = purchase_rate

            rec.diff = rec.so_rate - purchase_rate
            rec.d_amt = rec.diff * total_qty

    def _get_automatic_balancing_account(self):
        self.ensure_one()
        if self.ref and "TDS" in self.ref:
            diff = sum(self.line_ids.mapped('balance'))
            if diff > 0:
                account = self.env['account.account'].search(
                    [('code', '=', '213202')], limit=1)
                if account:
                    return account.id
            if diff < 0:
                account = self.env['account.account'].search(
                    [('code', '=', '213201')], limit=1)
                if account:
                    return account.id
        return super()._get_automatic_balancing_account()

    @api.model
    def create(self, vals):
        mv = super().create(vals)
        rounding = self.env['account.cash.rounding'].search([('rounding_method', '=', 'HALF-UP')], limit=1)
        if rounding and not mv.invoice_cash_rounding_id:
            mv.invoice_cash_rounding_id = rounding.id
        return mv

    def _compute_is_sale_installed(self):
        sale_installed = 'sale' in self.env
        for rec in self:
            rec.is_sale_installed = bool(sale_installed)

    def _get_readonly_fields(self):
        fields = super()._get_readonly_fields()
        if 'invoice_date' in fields:
            fields.remove('invoice_date')
        return fields
    
    def write(self, vals):
        if 'invoice_date' in vals and self and all(move.id for move in self):
            posted_moves = self.filtered(lambda m: m.state == 'posted')
            
            if posted_moves:
                posted_moves.button_draft()
                res = super(AccountMove, posted_moves).write(vals)
                posted_moves.action_post()
                return res

        return super().write(vals)
    
    def action_post(self):
        res = super().action_post()
        for move in self.filtered(lambda m: m.auto_tds_apply and m.move_type in ('in_invoice','in_refund')):
            if not move.exists():
                continue
            tax = self.env['account.tax'].search([
                ('name', 'ilike', '0.1% TDS 194Q S'),
                ('type_tax_use', '=', 'purchase')
            ], limit=1)
            if not tax or not tax.exists():
                raise UserError("TDS Section 194Q not configured.")
            if move.line_ids.filtered(lambda l: l.tax_line_id.id == tax.id):
                continue
            wizard = self.env['l10n_in.withhold.wizard'].with_context(
                active_model='account.move',
                active_ids=[move.id]
            ).create({
                'tax_id': tax.id,
                'base': move.amount_untaxed,
            })
            wizard.action_create_and_post_withhold()
        return res

    # def action_post(self):
    #     res = super().action_post()
    #     for move in self:
    #         if move.auto_tds_apply and move.move_type in ('in_invoice', 'in_refund'):
    #             tax = self.env['account.tax'].search([
    #                 ('name', 'ilike', '0.1% TDS 194Q S'),
    #                 ('type_tax_use', '=', 'purchase')
    #             ], limit=1)
    #             if not tax:
    #                 raise UserError("TDS Section 194Q not configured.")

    #             wizard = self.env['l10n_in.withhold.wizard'].with_context(active_model='account.move', active_ids=move.ids
    #             ).create({
    #                 'tax_id': tax.id,
    #                 'base': move.amount_untaxed,
    #             })
    #             wizard.action_create_and_post_withhold()
    #     return res

    picking_id = fields.Many2one(
        'stock.picking',
        string='Delivery Order',
        index=True
    )
    delay_charge_count = fields.Integer(
    string="Delay Charges",
    compute="_compute_delay_charge_count"
    )

    def _compute_delay_charge_count(self):
        for move in self:
            move.delay_charge_count = self.env['invoice.delay.charge'].search_count([
                ('invoice_id', '=', move.id)
            ])

    def action_view_delay_charges(self):
        self.ensure_one()

        charges = self.env['invoice.delay.charge'].search([
            ('invoice_id', '=', self.id)
        ])

        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'invoice.delay.charge',
            'target': 'current',
        }

        if len(charges) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': charges.id,
            })
        else:
            action.update({
                'view_mode': 'list,form',
                'domain': [('id', 'in', charges.ids)],
            })

        return action

    # def action_post(self):
    #     res = super().action_post()
    #     for move in self:
    #         if move.state == 'posted':
    #             if move.move_type == 'out_invoice':
    #                 move._log_customer_invoice_whatsapp()
    #             elif move.move_type == 'in_invoice':
    #                 move._log_vendor_invoice_whatsapp()
    #     return res

    def _log_customer_invoice_whatsapp(self):
        self.ensure_one()

        items = []
        for line in self.invoice_line_ids:
            if line.quantity > 0:
                items.append(f"{line.product_id.display_name}, Qty {line.quantity} quintal")
        items_text = "\n".join(items) if items else "N/A"

        party = self.partner_id
        party_number = party.phone

        broker = False
        if self.invoice_line_ids:
            sale_lines = self.invoice_line_ids.mapped('sale_line_ids')
            if sale_lines:
                sale_order = sale_lines[0].order_id
                if sale_order.broker_allotment_id:
                    broker = sale_order.broker_allotment_id.partner_id

        invoice_number = self.name or 'Draft'
        invoice_date = self.invoice_date or 'Draft Date'

        message = (
            f"Customer Invoice Generated\n\n"
            f"Invoice No : {invoice_number}\n"
            f"Invoice Date : {invoice_date}\n"
            f"Party : {party.name if party else 'N/A'}\n"
            f"Broker : {broker.name if broker else 'N/A'}\n\n"
            f"Items:\n{items_text}"
        )

        if party_number:
            _logger.warning("Send To (PARTY): %s", party.name)
            _logger.warning("Contact Number: %s", party_number)
            _logger.warning("Message:\n%s", message)
            _logger.warning("---------------------------------------------")

        if broker and broker.phone:
            _logger.warning("Send To (BROKER): %s", broker.name)
            _logger.warning("Contact Number: %s", broker.phone)
            _logger.warning("Message:\n%s", message)
            _logger.warning("---------------------------------------------")



    def _log_vendor_invoice_whatsapp(self):
        self.ensure_one()

        items = []
        for line in self.invoice_line_ids:
            if line.quantity > 0:
                items.append(f"{line.product_id.display_name}, Qty {line.quantity} quintal")
        items_text = "\n".join(items) if items else "N/A"

        vendor = self.partner_id
        vendor_number = vendor.phone

        message = (
            f"Vendor Bill Generated\n\n"
            f"Vendor : {vendor.name if vendor else 'N/A'}\n"
            f"Bill No : {self.name or 'Draft'}\n"
            f"Bill Date : {self.invoice_date or 'Draft Date'}\n\n"
            f"Items:\n{items_text}"
        )

        if vendor_number:
            _logger.warning("Send To (VENDOR): %s", vendor.name)
            _logger.warning("Contact Number: %s", vendor_number)
            _logger.warning("Message:\n%s", message)
            _logger.warning("---------------------------------------------")


    # def _get_credit_delay_charge_account(self):
    #     account_id = self.env['ir.config_parameter'].sudo().get_param(
    #         'party_sale_modifier_hmrc.credit_delay_charge_account_id'
    #     )
    #     if not account_id:
    #         raise UserError("Please configure Credit Delay Charge Account in Accounting Settings.")
    #     return int(account_id)

    # def _get_same_tax_as_invoice(self):
    #     product = self.env.ref('party_sale_modifier_hmrc.product_overdue_credit_charge', raise_if_not_found=True)

    #     base_line = self.invoice_line_ids.filtered(
    #         lambda l: l.product_id and l.product_id.id != product.id and l.tax_ids
    #     )[:1]

    #     return base_line.tax_ids.ids if base_line else []

    def _get_same_tax_as_invoice(self):
        for line in self.invoice_line_ids:
            if line.tax_ids:
                return line.tax_ids.ids
        return []


    last_charged_upto_day = fields.Integer(string="Overdue Charge Applied Upto Day", default=0, copy=False)
    show_overdue_charge_button = fields.Boolean(string="Show Overdue Charge Button", compute='_compute_show_overdue_charge_button', store=True)

    @api.depends('state', 'invoice_date_due', 'amount_residual','last_charged_upto_day')
    def _compute_show_overdue_charge_button(self):
        today = date.today()
        for move in self:
            if move.move_type == 'out_invoice' and move.state == 'posted' and move.amount_residual > 0:
                overdue_days = 0
                if move.invoice_date_due:
                    overdue_days = (today - move.invoice_date_due).days
                move.show_overdue_charge_button = overdue_days > move.last_charged_upto_day
            else:
                move.show_overdue_charge_button = False

    def action_add_overdue_credit_delay_charge(self):
        self.ensure_one()

        if not self.show_overdue_charge_button:
            raise UserError("No new overdue invoice available for charging.")

        if not self.invoice_date_due:
            raise UserError("Invoice due date is not set.")

        today = date.today()
        overdue_days = (today - self.invoice_date_due).days

        # partner = self.partner_id

        # slabs = self.env['overdue.charge'].search([
        #     '|',
        #     ('partner_id', '=', partner.id),
        #     ('partner_id', '=', False)
        # ], order="from_day asc")

        charges = self.env['overdue.charge'].search([
            ('day', '=', overdue_days)
        ], limit=1)


        # if not slabs:
        #     raise UserError("No delay charge slab found for the current days of this customer.")
        
        # max_slab_day = 0
        # for slab in slabs:
        #     if slab.to_day > max_slab_day:
        #         max_slab_day = slab.to_day

        # if overdue_days > max_slab_day:
        #     raise UserError(
        #         f"Delay charge slab is defined only upto {max_slab_day} days. "
        #         f"Please Configure a new slab starting from {max_slab_day + 1} days."
        #     )

        if not charges:
            raise UserError(
                f"Delay charge not configured for {overdue_days} days."
            )

        quintal_qty = sum(self.invoice_line_ids.mapped('quantity'))
        if quintal_qty <= 0:
            raise UserError("Invoice quantity is zero.")

        product = self.invoice_line_ids[0].product_id if self.invoice_line_ids else False

        tax_ids = self._get_same_tax_as_invoice()
        taxes = self.env['account.tax'].browse(tax_ids)

        total_base_amount = 0.0
        slab_lines = []
        label = []
        last_day = self.last_charged_upto_day

        # for slab in slabs:
        #     label = ", ".join([
        #         f"{slab.from_day}-{slab.to_day} Days @ ₹{slab.charge_per_quintal}/Qtl"
        #         for slab in slabs if overdue_days >= slab.from_day
        #     ])

        #     if overdue_days < slab.from_day:
        #         continue

        #     start_day = max(slab.from_day, last_day + 1)
        #     end_day = min(slab.to_day, overdue_days)

        #     if end_day < start_day:
        #         continue

        #     days = end_day - start_day + 1

        #     amount = quintal_qty * slab.charge_per_quintal * days
        #     total_base_amount += amount

        #     slab_lines.append(
        #         f"{start_day} to {end_day} Days @ ₹{slab.charge_per_quintal}/Qtl = ₹{amount}"
        #     )

        #     last_day = end_day

        if overdue_days <= last_day:
            raise UserError("No new delay charge applicable.")

        per_day_charge = charges.charge_per_quintal

        total_base_amount = quintal_qty * per_day_charge

        label = f"Day {overdue_days} @ ₹{per_day_charge}/Qtl"

        if total_base_amount <= 0:
            raise UserError("No new delay charge applicable.")

        tax_amount = 0.0
        if taxes:
            tax_res = taxes.compute_all(
                total_base_amount,
                currency=self.currency_id,
                quantity=1,
                partner=self.partner_id
            )
            tax_amount = tax_res.get('total_included', 0.0) - tax_res.get('total_excluded', 0.0)

        total_amount_with_tax = total_base_amount + tax_amount

        existing_charge = self.env['invoice.delay.charge'].search([
            ('invoice_id', '=', self.id)
        ], limit=1)

        if existing_charge:
            existing_charge.write({
                # 'delay_amount': existing_charge.delay_amount + total_base_amount,
                # 'tax_amount': existing_charge.tax_amount + tax_amount,
                # 'total_amount_with_tax': existing_charge.total_amount_with_tax + total_amount_with_tax,
                'delay_amount': total_base_amount,
                'tax_amount': tax_amount,
                'total_amount_with_tax': total_amount_with_tax,

                'delay_days_to': overdue_days,
                'total_qty': quintal_qty,
                'product_id': product.id if product else False,
                'label': label,
            })
        else:
            self.env['invoice.delay.charge'].create({
                'invoice_id': self.id,
                # 'partner_id': partner.id,
                'total_qty': quintal_qty,
                'delay_days_to': overdue_days,
                'delay_amount': total_base_amount,
                'tax_amount': tax_amount,
                'total_amount_with_tax': total_amount_with_tax,
                'product_id': product.id if product else False,
                'label': label,
            })

        self.write({'last_charged_upto_day': overdue_days})


    # def action_add_overdue_credit_delay_charge(self):
    #     self.ensure_one()

    #     if self.state != 'posted' or self.move_type != 'out_invoice':
    #         raise UserError("Only posted customer invoices allowed.")

    #     if not self.invoice_date_due:
    #         raise UserError("Invoice due date not set.")

    #     today = date.today()
    #     overdue_days = max((today - self.invoice_date_due).days, 0)

    #     if overdue_days <= self.last_charged_upto_day:
    #         raise UserError("No new overdue days to charge.")

    #     product = self.env.ref('party_sale_modifier_hmrc.product_overdue_credit_charge', raise_if_not_found=True)
    #     base_lines = self.invoice_line_ids.filtered(lambda l: l.product_id and l.product_id.id != product.id)

    #     quintal_qty = sum(base_lines.mapped('quantity'))
    #     if quintal_qty <= 0:
    #         raise UserError("Invoice quantity is zero.")

    #     account_id = self._get_credit_delay_charge_account()
    #     tax_ids = self._get_same_tax_as_invoice()

    #     total_new_amount = 0.0
    #     for day in range(self.last_charged_upto_day + 1, overdue_days + 1):
    #         invoice = self.env['overdue.charge'].search([('from_day', '<=', day), ('to_day', '>=', day),], limit=1)
    #         if not invoice:
    #             raise UserError("No overdue charge Master found for current overdue days.")

    #         total_new_amount += quintal_qty * invoice.charge_per_quintal

    #     if total_new_amount <= 0:
    #         raise UserError("No charge calculated.")

    #     delay_line = self.invoice_line_ids.filtered(lambda l: l.product_id.id == product.id)[:1]
    #     self.button_draft()

    #     name = f"Credit Delay Charge (1–{overdue_days} Days)"
    #     if delay_line:
    #         delay_line.write({
    #             'name': name,
    #             'price_unit': delay_line.price_unit + total_new_amount,
    #             'quantity': 1,
    #             'account_id': account_id,
    #             'tax_ids': [(6, 0, tax_ids)],
    #         })
    #     else:
    #         self.env['account.move.line'].create({
    #             'move_id': self.id,
    #             'product_id': product.id,
    #             'name': name,
    #             'quantity': 1,
    #             'price_unit': total_new_amount,
    #             'account_id': account_id,
    #             'tax_ids': [(6, 0, tax_ids)],
    #         })
    #     self.last_charged_upto_day = overdue_days
    #     self.action_post()


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _create_invoices(self, grouped=False, final=False):
        invoices = super()._create_invoices(grouped=grouped, final=final)

        for order in self:
            done_pickings = order.picking_ids.filtered(
                lambda p: p.state == 'done' and p.picking_type_id.code == 'outgoing'
            )

            for invoice in invoices.filtered(lambda i: i.invoice_origin == order.name):
                if done_pickings:
                    invoice.picking_id = done_pickings[-1].id

        return invoices

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_stock_open_valued_locations(self):
        pass


    credit_delay_charge_account_id = fields.Many2one('account.account', string="Credit Delay Charge Account", config_parameter='party_sale_modifier_hmrc.credit_delay_charge_account_id')
    freight_expense_account_id = fields.Many2one('account.account', string="Freight Expense Account",domain="[('account_type','=','expense')]",config_parameter='party_sale_modifier_hmrc.freight_expense_account_id')
    freight_payable_account_id = fields.Many2one('account.account', string="Freight Payable Account",domain="[('account_type','=','liability_payable')]",config_parameter='party_sale_modifier_hmrc.freight_payable_account_id')
    freight_journal_id = fields.Many2one('account.journal',string="Freight Journal",domain="[('type','=','general')]",config_parameter='party_sale_modifier_hmrc.freight_journal_id')

class InvoiceDelayCharge(models.Model):
    _name = "invoice.delay.charge"
    _description = "Invoice Delay Charge History"
    _order = "id desc"
    _rec_name = "product_id"


    invoice_id = fields.Many2one('account.move', string="Invoice", readonly=True)
    partner_id = fields.Many2one('res.partner', string="Party", readonly=True)
    total_qty = fields.Float(string="Total Qty (Quintal)", readonly=True)
    rate_per_quintal = fields.Float(string="Delay Charge Per Quintal", readonly=True)
    delay_days_to = fields.Integer(string="No. Of Delay Days", readonly=True)
    delay_amount = fields.Float(string="Delay Charge Amount", readonly=True)
    date = fields.Date(string="Charge Date", default=fields.Date.today, readonly=True)

    currency_id = fields.Many2one(
        'res.currency',
        related='invoice_id.currency_id',
        store=True,
        readonly=True
    )

    product_id = fields.Many2one(
        'product.product',
        string="Item",
        readonly=True
    )

    tax_amount = fields.Float(string="Tax Amount", readonly=True)
    total_amount_with_tax = fields.Float(string="Total Amount (Inc. Tax)", readonly=True)
    label = fields.Char(string="Delay Charge", readonly=True)


class AccountAccount(models.Model):
    _inherit = "account.account"

    current_rate = fields.Float(string="Current Rate")


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    picking_id = fields.Many2one('stock.picking')

    @api.model
    def create(self, vals):
        record = super().create(vals)

        if record.move_id.invoice_origin:
            sale = self.env['sale.order'].search([
                ('name', '=', record.move_id.invoice_origin)
            ], limit=1)

            if sale:
                pickings = sale.picking_ids.filtered(lambda p: p.state == 'done')

                if len(pickings) == 1:
                    record.picking_id = pickings.id

                elif pickings:
                    record.picking_id = pickings[0].id

        return record