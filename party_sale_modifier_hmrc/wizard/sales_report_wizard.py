from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
import io
import xlsxwriter 
from datetime import datetime


class SalesReportWizard(models.TransientModel):
    _name = 'sales.report.wizard'

    from_date = fields.Date(required=True)
    to_date = fields.Date(required=True)

    line_ids = fields.One2many(
        'sales.report.wizard.line',
        'wizard_id'
    )
    select_all = fields.Boolean(string="")

    show_date = fields.Boolean(compute="_compute_show_date")

    @api.depends('from_date', 'to_date')
    def _compute_show_date(self):
        for rec in self:
            rec.show_date = rec.from_date != rec.to_date

    @api.onchange('select_all')
    def _onchange_select_all(self):
        for line in self.line_ids:
            line.is_selected = self.select_all

    @api.onchange('from_date', 'to_date')
    def _onchange_dates(self):
        if not self.from_date or not self.to_date:
            return

        self.line_ids = [(5, 0, 0)]

        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', self.from_date),
            ('invoice_date', '<=', self.to_date)
        ])

        lines = []

        for invoice in invoices:
            sale = invoice.invoice_origin and self.env['sale.order'].search([
                ('name', '=', invoice.invoice_origin)
            ], limit=1)
           
            for line in invoice.invoice_line_ids:

                taxes = line.tax_ids.compute_all(
                    line.price_unit,
                    currency=invoice.currency_id,
                    quantity=line.quantity,
                    product=line.product_id,
                    partner=invoice.partner_id
                )

                cgst = sgst = igst = 0.0

                for tax in taxes['taxes']:
                    name = tax.get('name', '').lower()

                    if 'cgst' in name:
                        cgst += tax['amount']
                    elif 'sgst' in name:
                        sgst += tax['amount']
                    elif 'igst' in name:
                        igst += tax['amount']

                # picking = sale.picking_ids.filtered(lambda p: p.state == 'done')[:1]

                # freight = 0.0

                # if picking:
                #     freight_line = self.env['freight.charge.line'].search([
                #         ('picking_id', '=', picking.id)
                #     ], limit=1)
                #     freight = freight_line.total_amount if freight_line else 0.0

                # freight = sum(line.picking_id.freight_charge_line_ids.mapped('total_amount')) if line.picking_id else 0.0
                freight = 0.0
                if line.picking_id:
                    moves = self.env['account.move'].search([
                        ('picking_id', '=', line.picking_id.id),
                        ('state', '=', 'posted'),
                        ('ref', 'ilike', 'Freight')
                    ])
                    freight = sum(moves.mapped('amount_total'))

                purchase_rate = sale.po_rate if sale and sale.po_rate else 0.0
                if purchase_rate:
                    diff = line.price_unit - purchase_rate

                    if sale and sale.rate_type and sale.rate_type.upper() == 'FOR':
                        diff -= freight
                    # difference = line.price_unit - purchase_rate
                    # diff = (diff * line.quantity) / 10
                else:
                    diff = 0.0
                # purchase_rate = sale.po_rate if sale else 0.0
                # diff = line.price_unit - purchase_rate

                # if sale and sale.rate_type and sale.rate_type.upper() == 'FOR':
                #     diff -= freight
                # diff = (diff * line.quantity) / 10

                sale_line = line.sale_line_ids[:1]

                cr_days = sale_line.delay_days if sale_line else 0

                advance = 0.0

                lines.append((0, 0, {
                    'invoice_date': invoice.invoice_date,
                    'invoice_no': invoice.name,

                    'customer_name': f"{invoice.partner_id.name}, {invoice.partner_id.city or ''}",
                    'broker': sale.broker_id.name.split(' ')[0] if sale and sale.broker_id else '',

                    'product_id': line.product_id.id,

                    'qty': line.quantity,
                    'rate': line.price_unit,
                    'value': line.price_subtotal,

                    'cgst': cgst,
                    'sgst': sgst,
                    'igst': igst,

                    'total': line.price_total,
                    'diff': diff,

                    'type': sale.rate_type if sale else '',
                    'cr_days': cr_days,

                    'frt': freight,
                    'advance': advance,
                    'total_pay': freight - advance,

                    'vehicle_no': line.picking_id.vehicle_number if line.picking_id else '',
                }))

        self.line_ids = lines

    def action_print(self):
        selected_lines = self.line_ids.filtered(lambda l: l.is_selected)

        if not selected_lines:
            raise UserError("Please select at least one record")

        return self.env.ref('party_sale_modifier_hmrc.sales_report_action').with_context(date_from=self.from_date,date_to=self.to_date).report_action(selected_lines)


    def action_excel(self):
        selected_lines = self.line_ids.filtered(lambda l: l.is_selected)

        if not selected_lines:
            raise UserError("Please select at least one record")

        show_date = self.from_date != self.to_date

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Sales Report')

        title_format = workbook.add_format({'bold': True, 'align': 'center', 'font_size': 16})
        subtitle_format = workbook.add_format({'bold': True, 'align': 'center', 'font_size': 13})
        date_format = workbook.add_format({'align': 'center', 'font_size': 11})

        header_format = workbook.add_format({'bold': True, 'border': 1, 'align': 'center'})
        text_format = workbook.add_format({'border': 1, 'align': 'left','valign': 'vcenter'})
        number_format = workbook.add_format({'border': 1, 'num_format': '#,##0'})
        total_format = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#FFFF99'})
        total_format_only = workbook.add_format({'bold': True, 'border': 1, 'align': 'center', 'bg_color': '#FFF2CC'})

        date_str = ''
        if self.from_date and self.to_date:
            date_str = f"{self.from_date.strftime('%d-%b-%y')} - {self.to_date.strftime('%d-%b-%y')}"

        last_col = 18 if show_date else 17

        sheet.merge_range(0, 0, 0, last_col, 'TG Sugars LTD', title_format)
        sheet.merge_range(1, 0, 1, last_col, 'Sales Report', subtitle_format)
        sheet.merge_range(2, 0, 2, last_col, date_str, date_format)

        col = 0
        if show_date:
            sheet.write(3, col, 'Inv Date', header_format)
            col += 1

        # headers = [
        #     'Inv No', 'Customer', 'Broker', 'Item',
        #     'Qty', 'Type', 'SO Rate', 'Value',
        #     'CGST', 'SGST', 'IGST', 'Total',
        #     'Diff', 'Cr Days', 'Frt', 'Advance', 'Total Pay', 'Vehicle No'
        # ]
        headers = [
            'Inv No', 'Customer', 'Broker',
            'Qty', 'Type', 'SO Rate', 'Value',
            'CGST', 'SGST', 'IGST', 'Diff', 'Cr Days','Total'
        ]

        for h in headers:
            sheet.write(3, col, h, header_format)
            col += 1

        row = 4

        total_qty = total_value = total_total = 0
        total_cgst = total_sgst = total_igst = 0
        total_diff = total_frt = total_pay = 0

        max_customer_len = 0

        for line in selected_lines:

            col = 0

            if show_date:
                sheet.write(row, col, str(line.invoice_date or ''), text_format)
                col += 1

            sheet.write(row, col, line.invoice_no or '', text_format); col += 1
            # sheet.write(row, col, line.customer_name or '', text_format); col += 1

            product = line.product_id.name or ''
            vehicle = line.vehicle_no or ''
            freight = round(line.frt or 0)
            advance = round(line.advance or 0)
            total_pay = round(line.total_pay or 0)

            second_line = f"{product}, {vehicle}, {freight}-{advance}={total_pay}"

            # customer_text = f"{line.customer_name or ''} \r\n {second_line}"
            # sheet.write(row, col, customer_text, text_format)

            customer_col = col
            sheet.write(row, col, line.customer_name or '', text_format)

            col += 1

            # sheet.set_row(row, 30)

            sheet.write(row, col, line.broker or '', text_format); col += 1
            # sheet.write(row, col, line.product_id.name or '', text_format); col += 1

            sheet.write(row, col, line.qty or 0, number_format); col += 1
            sheet.write(row, col, line.type or '', text_format); col += 1
            sheet.write(row, col, line.rate or 0, number_format); col += 1
            sheet.write(row, col, line.value or 0, number_format); col += 1

            sheet.write(row, col, line.cgst or 0, number_format); col += 1
            sheet.write(row, col, line.sgst or 0, number_format); col += 1
            sheet.write(row, col, line.igst or 0, number_format); col += 1
            sheet.write(row, col, line.diff or 0, number_format); col += 1
            sheet.write(row, col, line.cr_days or 0, number_format); col += 1

            sheet.write(row, col, line.total or 0, number_format); col += 1

            # sheet.write(row, col, line.frt or 0, number_format); col += 1
            # sheet.write(row, col, line.advance or 0, number_format); col += 1
            # sheet.write(row, col, line.total_pay or 0, number_format); col += 1

            # sheet.write(row, col, line.vehicle_no or '', text_format)
            sheet.write(row + 1, customer_col, second_line, text_format)

            sheet.set_row(row, 20)
            sheet.set_row(row + 1, 18)

            row += 1

            # totals
            total_qty += line.qty or 0
            total_value += line.value or 0
            total_total += line.total or 0

            total_cgst += line.cgst or 0
            total_sgst += line.sgst or 0
            total_igst += line.igst or 0

            # total_diff += line.diff or 0
            line_diff_total = (line.diff or 0) * (line.qty or 0) / 10
            total_diff += line_diff_total
            # total_frt += line.frt or 0
            # total_pay += line.total_pay or 0

            row += 1

        col = 0

        if show_date:
            col = 1

        sheet.merge_range(row, 0, row, col + 2, 'TOTAL', total_format_only)

        col = 0
        if show_date:
            col += 1

        col += 3

        sheet.write(row, col, total_qty, total_format); col += 1
        col += 2  # skip type + rate
        sheet.write(row, col, total_value, total_format); col += 1

        sheet.write(row, col, total_cgst, total_format); col += 1
        sheet.write(row, col, total_sgst, total_format); col += 1
        sheet.write(row, col, total_igst, total_format); col += 1
        sheet.write(row, col, total_diff, total_format); col += 1
        col += 1
        sheet.write(row, col, total_total, total_format); col += 1

        col += 1
        # sheet.write(row, col, total_frt, total_format); col += 2
        # sheet.write(row, col, total_pay, total_format)

        # sheet.set_column(0, last_col, 15)

        customer_col = 1 if not show_date else 2

        if customer_col > 0:
            sheet.set_column(0, customer_col - 1, 20)

        sheet.set_column(customer_col, customer_col, 50)

        if customer_col < last_col:
             sheet.set_column(customer_col + 1, last_col, 20)

        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'Sales_Report.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }


class SalesReportWizardLine(models.TransientModel):
    _name = 'sales.report.wizard.line'
    _description = 'Sales Report Wizard Line'

    wizard_id = fields.Many2one('sales.report.wizard')

    is_selected = fields.Boolean(string="Select")
    invoice_date = fields.Date(string="Inv Date")
    invoice_no = fields.Char(string="Inv No")
    # sale_id = fields.Many2one('sale.order', string="Inv No")

    customer_name = fields.Char(string="Customer / City")
    broker = fields.Char(string="Broker")

    product_id = fields.Many2one('product.product', string="Item Name")

    qty = fields.Float(string="Qty")
    rate = fields.Float(string="SO Rate")
    value = fields.Float(string="Value")

    cgst = fields.Float(string="CGST Amt")
    sgst = fields.Float(string="SGST Amt")
    igst = fields.Float(string="IGST Amt")

    total = fields.Float(string="Total")
    diff = fields.Float(string="Diff")

    cr_days = fields.Integer(string="Cr Days")
    frt = fields.Float(string="Frt")
    advance = fields.Float(string="Advance (Less)")
    total_pay = fields.Float(string="Total to Pay")

    vehicle_no = fields.Char(string="Vehicle No")
    type = fields.Char(string="Type")
