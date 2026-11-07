# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>:wink:
# See LICENSE file for full copyright and licensing details.
#################################################################################

import logging

from odoo import models,   _
from odoo.tools.misc import formatLang, get_lang
import xml.etree.ElementTree as gfg
import xml.dom.minidom

_logger = logging.getLogger(__name__)

class Invoice(models.Model):

    _inherit = "account.move"

    def _display_address(self, partner):
        # get the information that will be injected into the display format
        # get the address format
        address_format = partner._get_address_format()
        args = {
            'street': partner.street or '',
            'street2': partner.street2 or '',
            'city': partner.city or '',
            'zip': partner.zip,
            'state_code': '',
            'state_name': '',
            'country_code': '',
            'country_name': '',
            'company_name': '',
        }
        return address_format % args

    def get_taxes_amount(self, default_tax):
        res = {}
        default_tax = default_tax
        tax_balance_multiplicator = -1 if self.is_inbound(True) else 1
        for line in self.line_ids.filtered(lambda line: line.tax_line_id):
            amount = tax_balance_multiplicator * (line.amount_currency if line.currency_id else line.balance)
            amount = round(amount, 2)
            if res.get(line.tax_line_id.name):
                res[line.tax_line_id.name]['amount'] += amount
            else:
                res[line.tax_line_id.name] = {'name':line.tax_line_id.tally_ledger_name or default_tax ,'amount': amount, 'percent': line.tax_line_id.amount, 'tally_ledger_name': True if line.tax_line_id.tally_ledger_name else False}
        return res

    def _line_by_categories(self, local, missing_list, configuration):
        default_category = configuration.tally_category_ledger
        ledger_by = configuration.ledger_by
        lines_by_category = {}
        for line in self.invoice_line_ids:
            id = line.product_id.id
            ledgername = line.product_id.local_tally_ledger if local else line.product_id.export_tally_ledger
            if ledger_by == 'category':
                id = line.product_id.categ_id.id
                ledgername = line.product_id.categ_id.local_tally_ledger if local else line.product_id.categ_id.export_tally_ledger
            if lines_by_category.get(id):
                lines_by_category[id]['amount'] += line.price_subtotal
                lines_by_category[id]['total_amount'] += line.credit
            else:
                lines_by_category[id] = {'total_amount':line.credit,'amount': line.price_subtotal,'ledgername': ledgername or default_category}
                if not ledgername:
                    if local:
                        if  ledger_by == 'product':
                            if '<b>Product - %s</b>: Tally Local Ledger'%(line.product_id.name) not in missing_list:
                                missing_list.append('<b>Product - %s</b>: Tally Local Ledger'%(line.product_id.name))
                        else:
                            if '<b>Product Category- %s</b>: Tally Local Ledger'%(line.product_id.name) not in missing_list:
                                missing_list.append('<b>Product Category - %s</b>: Tally Local Ledger'%(line.product_id.categ_id.name))
                    else:
                        if  ledger_by == 'product':
                            if '<b>Product - %s</b>: Tally Export Ledger'%(line.product_id.name) not in missing_list:
                                missing_list.append('<b>Product - %s</b>: Tally Local Ledger'%(line.product_id.name))
                        else:
                            if '<b>Product Category- %s</b>: Tally Export Ledger'%(line.product_id.name) not in missing_list:
                                missing_list.append('<b>Product Category - %s</b>: Tally Local Ledger'%(line.product_id.categ_id.name))
        return lines_by_category

    def _get_tally_fields(self,field_mapping_lines_ids):
        field_mapping_model=self.env['tally.mapping.line'].search_read([('id','in',field_mapping_lines_ids),('fixed','=',False)],['model_field_id'])
        field_mapping_model_ids=[x.get('model_field_id')[0] for x in field_mapping_model]
        field_mapping_model_name_ids=self.env['ir.model.fields'].sudo().search_read([('id','in',field_mapping_model_ids)],['name'])
        field_mapping_model_name=[x.get('name') for x in field_mapping_model_name_ids]
        return field_mapping_model_name

    def GenerateXML(self, configuration):
        field_mapping_model_name = self._get_tally_fields(configuration.field_mapping_id.tally_mapping_line_ids.ids)
        root = gfg.Element("ENVELOPE")
        header = gfg.Element("HEADER")
        root.append(header)
        tallyrequest = gfg.SubElement(header, "TALLYREQUEST")
        tallyrequest.text = "Import Data"
        body = gfg.Element("BODY")
        root.append(body)
        importdata = gfg.SubElement(body, "IMPORTDATA")
        requestdata = gfg.SubElement(importdata, "REQUESTDATA")
        tallymessage = gfg.SubElement(requestdata, "TALLYMESSAGE")
        missing_list = []
        default_journal = configuration.tally_journal_ledger
        for invoice in self:
            invoice_data = invoice.read(field_mapping_model_name)[0]
            currencyObj = False
            local = True
            if invoice.partner_id and invoice.partner_id.country_id and invoice.partner_id.country_id.code != 'IN':
                currencyObj = self.env['res.currency'].sudo().search([('name', '=', 'INR')], limit=1)
                local = False
            for line in invoice.line_ids:
                _logger.info("=========%r",line.display_type  )
            pay_term_lines = invoice.line_ids\
            .filtered(lambda line: line.display_type =='payment_term')
            journal = False
            for partial in pay_term_lines.matched_debit_ids:
                journal = partial.debit_move_id.journal_id
                break
            for partial in pay_term_lines.matched_credit_ids:
                journal = partial.credit_move_id.journal_id
                break
            voucher = gfg.SubElement(tallymessage, "VOUCHER",VCHTYPE='Sales',ACTION='Create',OBJVIEW='Invoice Voucher View')
            partyname = gfg.SubElement(voucher, "PARTYNAME")
            if invoice.partner_id.name:
                partyname.text = invoice.partner_id.name 
            address = gfg.SubElement(voucher, "ADDRESS")
            address.text = invoice._display_address(invoice.partner_id)
            company = invoice.company_id
            if local:
                gstregistrationtype = gfg.SubElement(voucher, "GSTREGISTRATIONTYPE")
                gst_treatment = 'Unregistered'
                if invoice.l10n_in_gst_treatment == 'regular':
                    gst_treatment = 'Regular'
                    partygstin = gfg.SubElement(voucher, "PARTYGSTIN")
                    partygstin.text = invoice.partner_id.vat
                    consigneegstin = gfg.SubElement(voucher, "CONSIGNEEGSTIN")
                    consigneegstin.text = invoice.partner_id.vat
                gstregistrationtype.text = gst_treatment
                placeofsupply = gfg.SubElement(voucher, "PLACEOFSUPPLY")
                consigneestatename = gfg.SubElement(voucher, "CONSIGNEESTATENAME")
                statename = gfg.SubElement(voucher, "STATENAME")
                if invoice.partner_id.state_id:
                    state = invoice.partner_id.state_id.name
                else:
                    state = company.state_id.name if company.state_id else 'Uttar Pradesh'
                placeofsupply.text = state
                consigneestatename.text = state
                statename.text = state
            else:
                consigneecountryname = gfg.SubElement(voucher, "CONSIGNEECOUNTRYNAME")
                if invoice.partner_id.country_id:
                    consigneecountryname.text = invoice.partner_id.country_id.name
            vouchertypename = gfg.SubElement(voucher, "VOUCHERTYPENAME")
            vouchertypename.text = 'Sales'
            partyledgername = gfg.SubElement(voucher, "PARTYLEDGERNAME")
            journal_name = default_journal
            if journal:
                if local:
                    if not journal.tally_ledger_local:
                        if "<b>Journal %s</b>: Tally Local Ledger "%(journal.name) not in missing_list:
                            missing_list.append("<b>Journal %s</b>: Tally Local Ledger "%(journal.name))
                    else:
                        journal_name = journal.tally_ledger_local
                else:
                    if not journal.tally_ledger_export:
                        if "<b>Journal %s</b>: Tally Export Ledger"%(journal.name) in missing_list:
                            missing_list.append("<b>Journal %s</b>: Tally Export Ledger"%(journal.name))
                    else:
                        journal_name = journal.tally_ledger_export
            partyledgername.text = journal_name
            basicbuyername = gfg.SubElement(voucher, "BASICBUYERNAME")
            if invoice.partner_id.name:
                basicbuyername.text = invoice.partner_id.name 
            basicbuyeraddress = gfg.SubElement(voucher, "BASICBUYERADDRESS")
            basicbuyeraddress.text = invoice._display_address(invoice.partner_id)
            countryofresidence = gfg.SubElement(voucher, "COUNTRYOFRESIDENCE")
            if invoice.partner_id.country_id:
                countryofresidence.text = invoice.partner_id.country_id.name
            else:
                countryofresidence.text = 'India'
            isinvoice = gfg.SubElement(voucher, "ISINVOICE")
            isinvoice.text = 'Yes'
            for i in configuration.field_mapping_id.tally_mapping_line_ids:
                key=i.tally_field_id.name
                if i.fixed:
                    value=i.fixed_text
                else: 
                    if i.model_field_id.ttype == 'many2one':
                        v_name=invoice_data.get(i.model_field_id.name)
                        if v_name:
                            value=v_name[1]
                        else:
                            value = False or i.default
                    elif i.model_field_id.ttype == 'date':
                        date_val = invoice_data.get(i.model_field_id.name)
                        if date_val:
                            value = date_val.strftime('%Y%m%d')
                        else:
                            value = ''

                    else:
                        value=invoice_data.get(i.model_field_id.name) or i.default
                data = gfg.SubElement(voucher, key)
                if not value:
                    data.text = invoice.name
                    missing_list.append("%s invoice %s is missing"%(i.model_field_id.name, invoice.name))
                else:
                    data.text = value
            ledgerentries_list = gfg.SubElement(voucher, "LEDGERENTRIES.LIST")
            ledgername = gfg.SubElement(ledgerentries_list, "LEDGERNAME")
            ledgername.text = journal_name
            isdeemedpositive = gfg.SubElement(ledgerentries_list, "ISDEEMEDPOSITIVE")
            isdeemedpositive.text = 'Yes'
            ispartyledger = gfg.SubElement(ledgerentries_list, "ISPARTYLEDGER")
            ispartyledger.text = 'Yes'
            amount = gfg.SubElement(ledgerentries_list, "AMOUNT")
            order_currencyObj = invoice.currency_id
            lang_obj = get_lang(self.env)
            # res = lang_obj.format('%.' + str(2) + 'f', -(invoice.amount_total or 1.0))
            amount_value = float(invoice.amount_total or 0.0)
            amount_value = -amount_value
            res = "%.2f" % amount_value
            ordered_amount = '%s %s' % (res, order_currencyObj.symbol)
            total = float(invoice.amount_total or 0.0)


            # ordered_amount = '%s %s' % (res, order_currencyObj.symbol)
            # total = str(invoice.amount_total or 1.0)
            # if currencyObj != order_currencyObj:
            #     amount_total = invoice.amount_total_signed or 1.0
            #     total = formatLang(self.env, -(amount_total), currency_obj=currencyObj)
            # if local:
            #     # amount.text = '%s'%(total)
            #     amount.text = format(total or 0.0, '.2f')
            # else:
            #     # amount.text = '%s = %s'%(ordered_amount,total)
            #     total = float(total or 0.0)
            #     amount.text = format(total, '.2f')
            if currencyObj and currencyObj != order_currencyObj:
                total_signed = float(invoice.amount_total_signed or 0.0)
                total = float(total_signed)

            if local:
                amount.text = "%.2f" % total
            else:
                amount.text = "%s = %.2f" % (ordered_amount, total)

            if configuration.bill_allocation:
                billallocations = gfg.SubElement(ledgerentries_list, "BILLALLOCATIONS.LIST")
                billallocations_name = gfg.SubElement(billallocations, "NAME")
                billallocations_name.text = invoice.name
                billallocations_billtype = gfg.SubElement(billallocations, "BILLTYPE.LIST")
                billallocations_billtype.text = "New Ref"
                billallocations_amount = gfg.SubElement(billallocations, "AMOUNT")
                if local:
                    billallocations_amount.text = '%s'%(total)
                else:
                    billallocations_amount.text = '%s = %s'%(ordered_amount,total)
            lines_by_category = invoice._line_by_categories(local, missing_list, configuration)
            amount = 1.0
            count = 0
            for category in lines_by_category:
                amount_total = lines_by_category.get(category).get('amount')
                total_amount = lines_by_category.get(category).get('total_amount')
                if invoice.amount_total == 0 and count == 0:
                    amount_total = total_amount = amount
                    count = 1
                ledgername_data = lines_by_category.get(category).get('ledgername')
                lang_obj = get_lang(self.env)
                # res = lang_obj.format('%.' + str(2) + 'f', amount_total)
                amount_total = float(amount_total or 0.0)
                res = "%.2f" % amount_total

                ordered_amount = '%s %s' % (res, order_currencyObj.symbol)
                total = total_amount
                if currencyObj != order_currencyObj:
                    total = formatLang(self.env, total, currency_obj=currencyObj)
                ledgerentries_list = gfg.SubElement(voucher, "LEDGERENTRIES.LIST")
                ledgername = gfg.SubElement(ledgerentries_list, "LEDGERNAME")
                ledgername.text = ledgername_data
                isdeemedpositive = gfg.SubElement(ledgerentries_list, "ISDEEMEDPOSITIVE")
                isdeemedpositive.text = 'No'
                ispartyledger = gfg.SubElement(ledgerentries_list, "ISPARTYLEDGER")
                ispartyledger.text = 'No'
                amount = gfg.SubElement(ledgerentries_list, "AMOUNT")
                gstovrdnnature = gfg.SubElement(ledgerentries_list, "GSTOVRDNNATURE")
                if local:
                    amount.text = str(amount_total)
                    state_code = invoice.partner_id.state_id.code
                    compnay_code = company.state_id.code
                    company.state_id
                    if not state_code or state_code == compnay_code:
                        gstovrdnnature.text = configuration.gstovrdnnature_local
                    else:
                        gstovrdnnature.text = configuration.gstovrdnnature_interstate
                else:
                    amount.text = '%s = %s'%(ordered_amount,total)
                    gstovrdnnature.text = configuration.gstovrdnnature_overseas
            if local:
                taxes = invoice.get_taxes_amount(configuration.tally_tax_ledger)
                for tax in taxes:
                    ledgerentries_list = gfg.SubElement(voucher, "LEDGERENTRIES.LIST")
                    ledgername = gfg.SubElement(ledgerentries_list, "LEDGERNAME")
                    ledgername.text = taxes.get(tax)['name']
                    basicrateofinvoicetax = gfg.SubElement(ledgerentries_list, "BASICRATEOFINVOICETAX")
                    basicrateofinvoicetax.text = str(taxes.get(tax)['percent'])
                    isdeemedpositive = gfg.SubElement(ledgerentries_list, "ISDEEMEDPOSITIVE")
                    isdeemedpositive.text = 'No'
                    ispartyledger = gfg.SubElement(ledgerentries_list, "ISPARTYLEDGER")
                    ispartyledger.text = 'No'
                    amount = gfg.SubElement(ledgerentries_list, "AMOUNT")
                    # amount.text = str(taxes.get(tax)['amount'])
                    tax_amt = float(taxes.get(tax)['amount'] or 0.0)
                    amount.text = "%.2f" % tax_amt

                    if not taxes.get(tax)['tally_ledger_name']:
                        if "<b>%s</b>: Tally Ledger"%(tax) not in missing_list:
                            missing_list.append("<b>%s</b>: Tally Ledger"%(tax) )
        xml_str = gfg.tostring(root, encoding='unicode')
        dom = xml.dom.minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml()
        return pretty_xml, missing_list
