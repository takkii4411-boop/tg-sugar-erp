from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
import io 
import xlsxwriter 


class PurchaseReportWizard(models.TransientModel):
    _name = 'purchase.report.wizard'

    from_date = fields.Date(required=True)
    to_date = fields.Date(required=True)

    @api.constrains('from_date', 'to_date')
    def _check_date_range(self):
        for rec in self:
            if rec.from_date and rec.to_date:
                if rec.to_date < rec.from_date:
                    raise ValidationError(
                        "To Date cannot be earlier than From Date.\n"
                        "Please select a date equal to or greater than From Date."
                    )


    line_ids = fields.One2many(
        'purchase.report.wizard.line',
        'wizard_id'
    )

    show_date = fields.Boolean(compute="_compute_show_date")

    @api.depends('from_date', 'to_date')
    def _compute_show_date(self):
        for rec in self:
            rec.show_date = rec.from_date != rec.to_date

    @api.onchange('from_date', 'to_date')
    def _onchange_dates(self):
        if not self.from_date or not self.to_date:
            return

        self.line_ids = [(5, 0, 0)]

        bills = self.env['account.move'].search([
            ('move_type', '=', 'in_invoice'),
            ('invoice_date', '>=', self.from_date),
            ('invoice_date', '<=', self.to_date),
            ('state', '==', 'posted')
        ])

        lines = []

        for bill in bills:
            for line in bill.invoice_line_ids:

                if not line.product_id:
                    continue

                qty = line.quantity or 0.0
                pur_rate = line.price_unit or 0.0
                value = qty * pur_rate

                taxes = line.tax_ids.compute_all(
                    pur_rate,
                    currency=bill.currency_id,
                    quantity=qty,
                    product=line.product_id,
                    partner=bill.partner_id
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

                cgst = round(cgst)
                sgst = round(sgst)
                igst = round(igst)

                total = round(taxes['total_included'])

                tds_amt = round(value * 0.001)

                net_amt = round(total - tds_amt)
                po_number = ''

                if line.purchase_line_id and line.purchase_line_id.order_id:
                    po_number = line.purchase_line_id.order_id.name

                lines.append((0, 0, {
                    'date': bill.invoice_date,
                    'vou_no': bill.name,
                    'bill_no': bill.ref or '',
                    'vendor_name': f"{bill.partner_id.name}, {bill.partner_id.city or ''}",
                    'po_number': po_number,
                    'product_id': line.product_id.id,

                    'qty': qty,
                    'pur_rate': pur_rate,
                    'value': value,

                    'cgst': cgst,
                    'sgst': sgst,
                    'igst': igst,

                    'total': total,
                    'tds_amt': tds_amt,
                    'net_amt': net_amt,

                    'vehicle_no': bill.vehicle_number if hasattr(bill, 'vehicle_number') else '',
                }))

        self.line_ids = lines

    def action_print(self):
        if not self.line_ids:
            raise UserError("No records to print")

        return self.env.ref('tender_booking.purchase_report_action').with_context(from_date=self.from_date,to_date=self.to_date).report_action(self)

    def action_excel(self):
        selected_lines = self.line_ids

        if not selected_lines:
            raise UserError("No records to export")

        show_date = self.from_date != self.to_date

    #     if not selected_lines:
    #         raise UserError("Please select at least one record")
            
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Purchase Report')

        title_format = workbook.add_format({'bold': True, 'align': 'center', 'font_size': 16})
        subtitle_format = workbook.add_format({'bold': True, 'align': 'center', 'font_size': 13})
        date_format = workbook.add_format({'align': 'center', 'font_size': 11})

        header_format = workbook.add_format({'bold': True, 'border': 1, 'align': 'center'})
        text_format = workbook.add_format({'border': 1})
        number_format = workbook.add_format({'border': 1, 'num_format': '#,##0'})
        total_format = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#FFFF99'})
        total_format_only = workbook.add_format({'bold': True, 'border': 1, 'align': 'center', 'bg_color': '#FFF2CC'})

        date_str = ''
        if self.from_date and self.to_date:
            date_str = f"{self.from_date.strftime('%d-%b-%y')} - {self.to_date.strftime('%d-%b-%y')}"

        last_col = 15 if show_date else 14

        sheet.merge_range(0, 0, 0, last_col, 'TG Sugars LTD', title_format)
        sheet.merge_range(1, 0, 1, last_col, 'Purchase Report', subtitle_format)
        sheet.merge_range(2, 0, 2, last_col, date_str, date_format)

        col = 0

        if show_date:
            sheet.write(3, col, 'Date', header_format)
            col += 1

        headers = [
            'Vou No', 'Bill No', 'Vendor Name', 'PO Number', 'Item Name',
            'Qty', 'Pur Rate', 'Value',
            'CGST', 'SGST', 'IGST',
            'Total', 'TDS Amt', 'Net Amt', 'Vehicle No'
        ]

        for h in headers:
            sheet.write(3, col, h, header_format)
            col += 1

        row = 4

        total_qty = total_value = total_total = 0
        total_cgst = total_sgst = total_igst = 0
        total_tds = total_net = 0

        for line in selected_lines:

            col = 0

            if show_date:
                sheet.write(row, col, str(line.date or ''), text_format)
                col += 1

            sheet.write(row, col, line.vou_no or '', text_format); col += 1
            sheet.write(row, col, line.bill_no or '', text_format); col += 1
            sheet.write(row, col, line.vendor_name or '', text_format); col += 1
            sheet.write(row, col, line.po_number or '', text_format); col += 1
            sheet.write(row, col, line.product_id.display_name or '', text_format); col += 1

            sheet.write(row, col, line.qty or 0, number_format); total_qty += line.qty or 0; col += 1
            sheet.write(row, col, line.pur_rate or 0, number_format); col += 1
            sheet.write(row, col, line.value or 0, number_format); total_value += line.value or 0; col += 1

            sheet.write(row, col, line.cgst or 0, number_format); total_cgst += line.cgst or 0; col += 1
            sheet.write(row, col, line.sgst or 0, number_format); total_sgst += line.sgst or 0; col += 1
            sheet.write(row, col, line.igst or 0, number_format); total_igst += line.igst or 0; col += 1

            sheet.write(row, col, line.total or 0, number_format); total_total += line.total or 0; col += 1
            sheet.write(row, col, line.tds_amt or 0, number_format); total_tds += line.tds_amt or 0; col += 1
            sheet.write(row, col, line.net_amt or 0, number_format); total_net += line.net_amt or 0; col += 1

            sheet.write(row, col, line.vehicle_no or '', text_format)

            row += 1

        col = 0

        if show_date:
            col = 1

        sheet.merge_range(row, 0, row, col + 4, 'TOTAL', total_format_only)

        col = 0
        if show_date:
            col += 1

        col += 5

        sheet.write(row, col, total_qty, total_format); col += 1
        col += 1
        sheet.write(row, col, total_value, total_format); col += 1

        sheet.write(row, col, total_cgst, total_format); col += 1
        sheet.write(row, col, total_sgst, total_format); col += 1
        sheet.write(row, col, total_igst, total_format); col += 1

        sheet.write(row, col, total_total, total_format); col += 1
        sheet.write(row, col, total_tds, total_format); col += 1
        sheet.write(row, col, total_net, total_format)

        sheet.set_column(0, last_col, 15)

        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'Purchase_Report.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }



class PurchaseReportWizardLine(models.TransientModel):
    _name = 'purchase.report.wizard.line'
    _description = 'purchase Report Wizard Line'

    wizard_id = fields.Many2one('purchase.report.wizard')
    date = fields.Date("Date")
    vou_no = fields.Char("Vou No")
    bill_no = fields.Char("Bill No")
    vendor_name = fields.Char("Vendor Name")

    product_id = fields.Many2one('product.product', "Item")

    qty = fields.Float("Qty")
    pur_rate = fields.Float("Pur Rate")
    value = fields.Float("Value")

    cgst = fields.Float("CGST")
    sgst = fields.Float("SGST")
    igst = fields.Float("IGST")

    total = fields.Float("Total")
    tds_amt = fields.Float("TDS")
    net_amt = fields.Float("Net Amount")

    vehicle_no = fields.Char("Vehicle No")
    po_number = fields.Char("PO Number")
