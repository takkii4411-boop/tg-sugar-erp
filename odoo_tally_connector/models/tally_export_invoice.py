# -*- coding: utf-8 -*-
##########################################################################
#
#  Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
##########################################################################

import base64
import logging

from datetime import datetime
import json

from odoo import api, fields, models,  _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class TallyExportInvoice(models.Model):
    _name = 'tally.export.invoice'
    _description = 'Tally Export Invoice History'
    _order = 'create_date desc'
    _inherit = ['mail.thread']

    @api.model
    def _default_invoice_ids(self):
        invoice_ids = self._context.get('active_model') == 'account.move' and self._context.get('active_ids') or []
        return invoice_ids

    @api.model
    def default_get(self, fields):
        rec = super(TallyExportInvoice, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        if active_model and active_model not in ['account.move']:
            raise UserError(
                _("Programmation error: the expected model for this action is 'emp.work.report'. The provided one is '%d'.") % active_model)
        # Checks on received invoice records
        if active_model and active_ids:
            records = self.env[active_model].browse(active_ids)
            if any (record.payment_state !='paid' for record in records):
                raise UserError(_('Please select only invoices which are in paid state.'))
        return rec

    name = fields.Char(string='Refrence', required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    state = fields.Selection([('draft', 'Draft'),
        ('in_progress', 'In Progress'), ('done', 'Done'),
        ('failed', 'Failed')], string='Status', default='draft', copy=False)
    invoice_ids = fields.Many2many('account.move', string='Invoices', copy=False)


    comment = fields.Text(string='Comment', copy=False)
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', copy=False)
    attachment_datas = fields.Binary('Document', related='attachment_id.datas')
    attachment_fname = fields.Char('Attachment Filename', related='attachment_id.name')
    date_from = fields.Date(string='Invoice Date From')
    date_to = fields.Date(string='Invoice Date To')
    configuration_id = fields.Many2one(
        'tally.configuration',
        string='Tally Configuration',
        )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        if self.filtered(lambda c: c.date_to and c.date_from > c.date_to):
            raise ValidationError(_('The date from must be anterior to the date to.'))

    invoice_domain = fields.Char(compute="_compute_invoice_domain", store=False)


    @api.depends('date_from', 'date_to')
    def _compute_invoice_domain(self):
        for rec in self:
            domain = [('move_type', '=', 'out_invoice'),
                    ('payment_state', '=', 'paid')]

            if rec.date_from:
                domain.append(('invoice_date', '>=', rec.date_from.strftime('%Y-%m-%d')))
            if rec.date_to:
                domain.append(('invoice_date', '<=', rec.date_to.strftime('%Y-%m-%d')))

            domain.append(('company_id', '=', self.env.company.id))

            rec.invoice_domain = json.dumps(domain)


    # @api.onchange('date_from', 'date_to')
    # def _onchange_date_range(self):
    #     if self.date_from and self.date_to:
    #         domain = [
    #             ('move_type', '=', 'out_invoice'),
    #             ('payment_state', 'in', ['paid', 'in_payment']),
    #             ('invoice_date', '>=', self.date_from),
    #             ('invoice_date', '<=', self.date_to),
    #             ('company_id', '=', self.env.company.id),
    #         ]
    #         invoices = self.env['account.move'].search(domain)
    #         self.invoice_ids = [(6, 0, invoices.ids)]
    #     else:
    #         self.invoice_ids = [(5, 0, 0)]



    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('tally.export.invoice')
        return super(TallyExportInvoice, self).create(vals_list)

    def in_queue(self):
        for obj in self:
            if obj.state == 'draft':
                if not obj.invoice_ids:
                    raise UserError(_("Sorry, you can't proceed this record, because no invoice has been linked in this record. Hence, first link the invoice to this record."))
                invoices = obj.invoice_ids
                result = obj.check_invoices(invoices)
                if result.get('status'):
                    obj.state = 'in_progress'
                else:
                    obj.state = 'failed'
                    obj.comment = result.get('msg')

    def check_invoices(self, invoices):
        result = {'status':True, 'msg':''}
        # inv = []
        # for invoice in invoices:
        #     if not (invoice.ref):
        #         inv.append(invoice.name)
        # if inv:
        #     msg = "Some invoices data are missing. (Missing data:- Payment Method, Store Order No, transaction number) " + ','.join(inv) 
        #     result.update({'status':False, 'msg':msg})
        return result

    def validate(self):
        for obj in self:
            obj.attachment_id.unlink()
            invoices = obj.invoice_ids.sorted('name')
            result = obj.check_invoices(invoices)
            if result.get('status'):
                xml_str, error_dict = invoices.GenerateXML(obj.configuration_id)
                base64Data = base64.b64encode(xml_str.encode())
                create_date = obj.create_date.strftime('%Y-%m-%d %H:%M:%S')
                zipAttachment = self.env[
                    'ir.attachment'].create({
                        'datas': base64Data,
                        'type': 'binary',
                        'res_model': 'tally.export.invoice',
                        'res_id': obj.id,
                        'store_fname': obj.name + '.xml',
                        'name': obj.name + '.xml',
                        'mimetype':'application/xml;charset=utf-8',
                    })
                obj.attachment_id = zipAttachment.id
                obj.comment = False
                if error_dict:
                    message = '<b>Missing Ledger are </b></br>'
                    message += "%s "%('<br/>'.join(error_dict))
                    obj.comment = message
            else:
                obj.state = 'failed'
                obj.comment = result.get('msg')

    def set_to_draft(self):
        for obj in self:
            if obj.state == 'failed':
                obj.state = 'draft'

    def set_to_done(self):
        for obj in self:
            if obj.state == 'in_progress':
                obj.state = 'done'

    def export_tally_invoice(self):
        logs = self.ids
        result = self.env.ref('tally_odoo_connector.action_export_tally_xml').sudo().read()[0]
        result['domain'] = [('id', 'in', logs.ids if logs else [])]
        return result
