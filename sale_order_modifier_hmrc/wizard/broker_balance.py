# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64
import io
import xlsxwriter

class BrokerBalanceReportWizard(models.TransientModel):
    _name = 'broker.balance.report.wizard'
    _description = 'Broker Balance Report Wizard'
    
    vendor_ids = fields.Many2many(
        'res.partner',
        string='Select Specific Broker',
        domain="[('supplier_rank', '>', 0)]",
        help="Leave empty to include all vendors"
    )
    
    date_from = fields.Date(
        string='Date From',
        required=True,
        default=fields.Date.context_today
    )
    
    date_to = fields.Date(
        string='Date To',
        required=True,
        default=fields.Date.context_today
    )
    
    # booking_no = fields.Char(string='Booking No')
    
    order_reference = fields.Char(string='Order Reference')
    
    state = fields.Selection([
        ('draft', 'RFQ'),
        ('purchase', 'Purchase Order'),
        ('locked', 'Locked'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status')
    
    report_line_ids = fields.One2many(
        'broker.balance.report.line',
        'wizard_id',
        string='Report Lines'
    )
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError("Date From cannot be greater than Date To!")
    
    @api.onchange('date_from')
    def _onchange_date_from(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            self.date_to = self.date_from
    
    def action_generate_report(self):
        self.ensure_one()
        
        self.report_line_ids.unlink()
        
        date_from_start = fields.Datetime.to_datetime(self.date_from)
        date_to_end = fields.Datetime.to_datetime(self.date_to).replace(hour=23, minute=59, second=59)
        
        domain = [
            # ('booking_date', '>=', date_from_start),
            # ('booking_date', '<=', date_to_end)
        ]
        
        if self.vendor_ids:
            domain.append(('partner_id', 'in', self.vendor_ids.ids))
        
        if self.order_reference:
            domain.append(('name', 'ilike', self.order_reference))
        
        if self.state:
            domain.append(('state', '=', self.state))
        
        broker_orders = self.env['broker.allotment'].search(domain, order='name desc')
        
        report_lines = []
        
        for order in broker_orders:
            for line in order.order_line:
                op_qty = line.product_uom_qty
                received_qty = line.qty_delivered
                unsold_bal_qty = op_qty - received_qty
                # brk_bal_qty = line.broker_qty - line.party_qty
                # p_bal_qty = unsold_bal_qty
                # total_bal = line.balance_qty
                ledger_bal = order.amount_total - order.amount_paid if hasattr(order, 'amount_paid') else order.amount_total
                
                report_lines.append({
                    'wizard_id': self.id,
                    # 'date': order.date_order.date() if order.date_order else False,
                    # 'booking_no': order.booking_no,
                    'order_no': order.name,
                    'item': line.product_id.name,
                    'rate': line.price_unit,
                    'op_qty': op_qty,
                    'unsold_bal_qty': line.balance_qty,
                    # 'brk_bal_qty': brk_bal_qty,
                    'p_bal_qty': line.party_qty,
                    'total_bal_os': line.balance_qty,
                    'ledger_bal': ledger_bal,
                    'vendor_id': order.partner_id.id,
                    'vendor_name': order.partner_id.name,
                    'order_id': order.id,
                    'tender_id': order.tender_id.id if order.tender_id else False,
                })
        
        if report_lines:
            self.env['broker.balance.report.line'].create(report_lines)
        else:
            raise ValidationError("No Broker found for the selected criteria!")
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'broker.balance.report.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }
    
    def action_export_report(self):
        self.ensure_one()
        
        if not self.report_line_ids:
            raise ValidationError("No data to export! Please generate the report first.")
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Outstanding Broker Balance')
        
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        number_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        text_format = workbook.add_format({'border': 1})
        
        headers = ['Date', 'Odoo Order No.', 'Broker Name', 'Item', 'Rate', 'OP Qty', 
                   'Unsold Bal Qty', 'Brk Bal Q', 'P Bal Q', 'Total Bal O/s', 'Ledger Bal']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        row = 1
        total_op_qty = 0
        total_unsold_bal_qty = 0
        total_brk_bal_qty = 0
        total_p_bal_qty = 0
        total_bal_os = 0
        total_ledger_bal = 0
        
        for line in self.report_line_ids:
            worksheet.write(row, 0, line.date.strftime('%Y-%m-%d') if line.date else '', text_format)
            worksheet.write(row, 1, line.booking_no or '', text_format)
            worksheet.write(row, 2, line.order_no or '', text_format)
            worksheet.write(row, 3, line.vendor_name or '', text_format)
            worksheet.write(row, 4, line.item or '', text_format)
            worksheet.write(row, 5, line.rate, number_format)
            worksheet.write(row, 6, line.op_qty, number_format)
            worksheet.write(row, 7, line.unsold_bal_qty, number_format)
            worksheet.write(row, 8, line.brk_bal_qty, number_format)
            worksheet.write(row, 9, line.p_bal_qty, number_format)
            worksheet.write(row, 10, line.total_bal_os, number_format)
            worksheet.write(row, 11, line.ledger_bal, number_format)
            
            total_op_qty += line.op_qty
            total_unsold_bal_qty += line.unsold_bal_qty
            total_brk_bal_qty += line.brk_bal_qty
            total_p_bal_qty += line.p_bal_qty
            total_bal_os += line.total_bal_os
            total_ledger_bal += line.ledger_bal
            
            row += 1
        
        total_format = workbook.add_format({
            'bold': True,
            'bg_color': '#FFFF00',
            'border': 1,
            'num_format': '#,##0.00'
        })
        
        worksheet.write(row, 5, 'Total:', header_format)
        worksheet.write(row, 6, total_op_qty, total_format)
        worksheet.write(row, 7, total_unsold_bal_qty, total_format)
        worksheet.write(row, 8, total_brk_bal_qty, total_format)
        worksheet.write(row, 9, total_p_bal_qty, total_format)
        worksheet.write(row, 10, total_bal_os, total_format)
        worksheet.write(row, 11, total_ledger_bal, total_format)
        
        worksheet.set_column('A:A', 12)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 20)
        worksheet.set_column('D:D', 25)
        worksheet.set_column('E:E', 30)
        worksheet.set_column('F:L', 15)
        
        workbook.close()
        output.seek(0)
        
        attachment = self.env['ir.attachment'].create({
            'name': 'Outstanding_broker_Balance_Report.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


class BrokerBalanceReportLine(models.TransientModel):
    _name = 'broker.balance.report.line'
    _description = 'Broker Balance Report Line'
    _order = 'order_no desc'
    
    wizard_id = fields.Many2one('broker.balance.report.wizard', string='Wizard', ondelete='cascade')
    date = fields.Date(string='Date')
    booking_no = fields.Char(string='Booking No')
    order_no = fields.Char(string='Order No')
    tender_id = fields.Many2one('purchase.order',string='Tender No')
    order_id = fields.Many2one('broker.allotment', string='Sale Order')
    item = fields.Char(string='Item')
    rate = fields.Float(string='Rate')
    op_qty = fields.Float(string='OP Qty')
    unsold_bal_qty = fields.Float(string='Unsold Bal Qty')
    brk_bal_qty = fields.Float(string='Brk bal Q')
    p_bal_qty = fields.Float(string='P Bal Q')
    total_bal_os = fields.Float(string='Total Bal O/s')
    ledger_bal = fields.Float(string='Ledger bal')
    vendor_id = fields.Many2one('res.partner', string='Broker ID')
    vendor_name = fields.Char(string='Broker Name')
    
    def action_open_record(self):
        self.ensure_one()
        if self.order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.order_id.id,
                'view_mode': 'form',
                'target': 'current'}
        else:
            raise ValidationError("No sale order linked to this record!")

class BrokerReleaseQtyWizard(models.TransientModel):
    _name = 'broker.release.qty.wizard'
    _description = 'Release Broker Quantity'

    broker_allotment_id = fields.Many2one(
        'broker.allotment',
        string="Broker Allotment",
        required=True
    )
    broker_line_id = fields.Many2one(
        'broker.allotment.line',
        string="Broker Line",
        required=True
    )

    total_balance_quantity = fields.Float(
        string="Total Balance Quantity",
        compute="_compute_total_balance_qty",
        readonly=True
    )
    release_qty = fields.Float(string="Release Quantity", required=True)

    @api.depends('broker_line_id.balance_qty')
    def _compute_total_balance_qty(self):
        for rec in self:
            rec.total_balance_quantity = rec.broker_line_id.balance_qty or 0.0

    def action_release_qty(self):
        self.ensure_one()

        line = self.broker_line_id
        if not line:
            raise UserError(_("Broker Line not found."))

        if self.release_qty <= 0:
            raise UserError(_("Release quantity must be greater than zero."))

        if self.release_qty > line.balance_qty:
            raise UserError(
                _("You cannot release more than balance quantity (%s).")
                % line.balance_qty
            )

        line.balance_qty -= self.release_qty
        # line.product_uom_qty -= self.release_qty 

        if line.po_line_id:
            line.po_line_id.balance_qty += self.release_qty
            line.po_line_id.broker_quantity -= self.release_qty

        line.broker_allotment_id.message_post(
            body=_(
                "Released %s quantity back to Tender."
            ) % self.release_qty
        )

        return {'type': 'ir.actions.act_window_close'}
