from odoo import models

class SalesReport(models.AbstractModel):
    _name = 'report.party_sale_modifier_hmrc.sales_report_template'

    def _get_report_values(self, docids, data=None):
        docs = self.env['sales.report.wizard.line'].browse(docids)

        wizard = docs.mapped('wizard_id')[:1]

        return {
            'docs': docs,
            'from_date': wizard.from_date if wizard else '',
            'to_date': wizard.to_date if wizard else '',
        }