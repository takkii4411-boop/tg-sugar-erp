from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, time
import io
import base64
import xlsxwriter
from odoo.http import request


class PoLotWizard(models.TransientModel):
    _name = 'po.lot.wizard'
    _description = 'PO Lot Report Wizard'

    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")

    @api.constrains('from_date', 'to_date')
    def _check_date(self):
        for rec in self:
            if rec.from_date and rec.to_date and rec.from_date > rec.to_date:
                raise ValidationError("From Date must be less than To Date.")

    def action_print_report(self):
        self.ensure_one()

        domain = [
            ('state', 'in', ['purchase', 'done']),
        ]

        if self.from_date:
            date_from = datetime.combine(self.from_date, time.min)
            domain.append(('booking_date', '>=', date_from))

        if self.to_date:
            date_to = datetime.combine(self.to_date, time.max)
            domain.append(('booking_date', '<=', date_to))

        orders = self.env['purchase.order'].search(domain)

        rows = []
        for rec in orders:
            deliveries = []

            for record in rec.party_allotment_ids.filtered(lambda s: s.state in ('sale', 'done')):
                for picking in record.picking_ids.filtered(lambda p: p.state == 'done' and p.picking_type_code == 'outgoing'):
                    so_rate = record.order_line[0].price_unit if record.order_line else 0.0
                    po_rate = rec.order_line[0].price_unit if rec.order_line else 0.0
                    qty = sum(picking.move_line_ids.mapped('qty_done')) if picking.move_line_ids else 0.0


                    freight = 0
                    freight_line = self.env['freight.charge.line'].search([('picking_id', '=', picking.id)], limit=1)
                    if freight_line:
                        freight = freight_line.total_amount or 0
                    diff = so_rate - po_rate + freight
                    inv_amount = diff * qty

                    invoice = record.invoice_ids.filtered(lambda inv: inv.state == 'posted')[:1]

                    invoice_no = invoice.name if invoice else ''
                    invoice_date = invoice.invoice_date if invoice else ''
                    cr_days = int(record.order_line[0].delay_days or 0) if record.order_line else 0
                    int_amount = round((inv_amount * 0.18 / 365) * cr_days, 2)
                    ngp = inv_amount - int_amount

                    deliveries.append({
                        # 'vch_no': picking.name,
                        # 'date': picking.date_done.date() if picking.date_done else '',
                        'vch_no': invoice_no,
                        'date': invoice_date,
                        'particulars': f"{record.partner_id.name}, {record.partner_id.city or ''}",
                        'broker': record.broker_allotment_id.partner_id.name if record.order_line else '',
                        'lorry_no': picking.vehicle_number or '',
                        'so_rate': record.order_line[0].price_unit if record.order_line else 0.0,
                        'qty': picking.move_line_ids.mapped('qty_done')[0] if picking.move_line_ids else 0.0,
                        'diff': (record.order_line[0].price_unit if record.order_line else 0.0) -
                                (rec.order_line[0].price_unit if rec.order_line else 0.0),
                        'd_amt': ((record.order_line[0].price_unit if record.order_line else 0.0) -
                                  (rec.order_line[0].price_unit if rec.order_line else 0.0)) *
                                 (picking.move_line_ids.mapped('qty_done')[0] if picking.move_line_ids else 0.0),
                        'cr_days': cr_days,
                        # 'int_invoice': record.invoice_ids.filtered(lambda inv: inv.state == 'posted').mapped('amount_residual') * 0.18 * 365 * record.payment_term_id.name,
                        # 'ngp': [((record.order_line[0].price_unit if record.order_line else 0.0) - (rec.order_line[0].price_unit if rec.order_line else 0.0)) * (picking.move_line_ids.mapped('qty_done')[0] if picking.move_line_ids else 0.0)] - [(record.invoice_ids.filtered(lambda inv: inv.state == 'posted').mapped('amount_residual') * 0.18 * 365 * record.payment_term_id.name)]
                        'int': int_amount,
                        'ngp': ngp,
                        
                        })
                    
            for line in rec.order_line:
                rows.append({
                    'booking_date': rec.booking_date.date() if rec.booking_date else '',
                    'tender_no': rec.name or '',
                    'partner_name': f"{rec.partner_id.name}, {rec.partner_id.city or ''}",               
                    'rate': line.price_unit or 0.0,
                    'deliveries': deliveries,
                    'ordered_qty': line.product_qty or 0.0, 
                })

        return self.env.ref('tender_booking.po_lot_report_pdf').with_context(
            date_from=self.from_date,
            date_to=self.to_date,
            rows=rows
        ).report_action(self)



    def action_export_excel(self):
        self.ensure_one()

        domain = [('state', 'in', ['purchase', 'done'])]

        if self.from_date:
            date_from = datetime.combine(self.from_date, time.min)
            domain.append(('booking_date', '>=', date_from))

        if self.to_date:
            date_to = datetime.combine(self.to_date, time.max)
            domain.append(('booking_date', '<=', date_to))

        orders = self.env['purchase.order'].search(domain)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('PO Lot Report')

        title_format = workbook.add_format({
            'bold': True, 'align': 'center', 'font_size': 16
        })

        header_format = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'center', 'bg_color': '#FFF2CC',
        })

        text_format = workbook.add_format({'border': 1})

        number_format = workbook.add_format({
            'border': 1,
            'num_format': '0'
        })

        center_text = workbook.add_format({
            'border': 1,
            'align': 'center'
        })

        total_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center',
            'bg_color': '#FFF2CC',
            'num_format': '0'
        })

        row = 0

     
        sheet.merge_range(row, 0, row, 10, self.env.company.name or '', title_format)
        row += 1

        sheet.merge_range(row, 0, row, 10, 'PO Lot Report', title_format)
        row += 1

        if self.from_date or self.to_date:
            date_format = workbook.add_format({'bold': True, 'align': 'center'})

            from_date = self.from_date.strftime('%d-%m-%Y') if self.from_date else ''
            to_date = self.to_date.strftime('%d-%m-%Y') if self.to_date else ''

            sheet.merge_range(row, 0, row, 10, f'From: {from_date}   To: {to_date}', date_format)
            row += 1


        row += 2

        for rec in orders:

            sheet.write(row, 0, 'PO No', header_format)
            sheet.write(row, 1, 'Date', header_format)
            sheet.write(row, 2, 'Party Name', header_format)
            sheet.write(row, 3, 'P Rate', header_format)
            sheet.write(row, 4, 'Tender QTY', header_format)

            row += 1

            for line in rec.order_line:
                sheet.write(row, 0, rec.name or '', text_format)
                sheet.write(row, 1, str(rec.booking_date.date()) if rec.booking_date else '', text_format)
                sheet.write(row, 2, rec.partner_id.name or '', text_format)
                sheet.write(row, 3, int(line.price_unit or 0), number_format)
                sheet.write(row, 4, int(line.product_qty or 0), number_format)
                row += 1

            sheet.write(row, 0, 'Inv No', header_format)
            sheet.write(row, 1, 'Date', header_format)
            sheet.write(row, 2, 'Particulars', header_format)
            sheet.write(row, 3, 'Broker', header_format)
            sheet.write(row, 4, 'Lorry No', header_format)
            sheet.write(row, 5, 'SO Rate', header_format)
            sheet.write(row, 6, 'Qty', header_format)
            sheet.write(row, 7, 'Diff', header_format)
            sheet.write(row, 8, 'D Amt', header_format)
            sheet.write(row, 9, 'Cr Days', header_format)
            sheet.write(row, 10, 'Int', header_format)
            sheet.write(row, 11, 'NGP', header_format)

            row += 1

            total_qty = 0
            total_amt = 0
            found = False

            for record in rec.party_allotment_ids.filtered(lambda s: s.state in ('sale', 'done')):
                for picking in record.picking_ids.filtered(lambda p: p.state == 'done'):

                    found = True

                    qty = sum(picking.move_line_ids.mapped('qty_done')) if picking.move_line_ids else 0
                    so_rate = record.order_line[0].price_unit if record.order_line else 0
                    po_rate = rec.order_line[0].price_unit if rec.order_line else 0
                    diff = so_rate - po_rate
                    amt = diff * qty

                    total_qty += qty
                    total_amt += amt

                    invoice = record.invoice_ids.filtered(lambda inv: inv.state == 'posted')[:1]

                    sheet.write(row, 0, invoice.name if invoice else '', text_format)
                    sheet.write(row, 1, str(invoice.invoice_date) if invoice else '', text_format)
                    sheet.write(row, 2, record.partner_id.name or '', text_format)
                    sheet.write(row, 3, record.broker_allotment_id.partner_id.name if record.broker_allotment_id else '', text_format)
                    sheet.write(row, 4, picking.vehicle_number or '', text_format)
                    sheet.write(row, 5, int(so_rate), number_format)
                    sheet.write(row, 6, int(qty), number_format)
                    sheet.write(row, 7, int(diff), number_format)
                    sheet.write(row, 8, int(amt), number_format)

                    cr_days = int(record.order_line[0].delay_days or 0) if record.order_line else 0
                    inv_amount = diff * qty
                    int_amount = round((inv_amount * 0.18 / 365) * cr_days, 2)
                    ngp = inv_amount - int_amount

                    sheet.write(row, 9, cr_days, number_format)
                    sheet.write(row, 10, int(int_amount), number_format)
                    sheet.write(row, 11, int(ngp), number_format)

                    row += 1

            if not found:
                sheet.merge_range(row, 0, row, 11, 'No Delivery Found', center_text)
                row += 1

            if found:
                sheet.merge_range(row, 0, row, 5, 'Total', total_format)
                sheet.write(row, 6, int(total_qty), total_format)
                sheet.write(row, 8, int(total_amt), total_format)

                sheet.write(row, 7, '', total_format)
                sheet.write(row, 9, '', total_format)
                sheet.write(row, 10, '', total_format)
                sheet.write(row, 11, '', total_format)

                row += 2

            row += 1

        sheet.set_column(0, 10, 18)

        workbook.close()
        output.seek(0)

        file_data = base64.b64encode(output.read())

        attachment = self.env['ir.attachment'].create({
            'name': 'PO Lot Report.xlsx',
            'type': 'binary',
            'datas': file_data,
            'res_model': self._name,
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }