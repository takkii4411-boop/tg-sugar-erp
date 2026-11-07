# -*- coding: utf-8 -*-
##########################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2017-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
##########################################################################

{
    'name': 'Odoo Tally Connector',
    'summary': 'Connecting Odoo with Tally for strong accounting management!',
    'category': 'Accounting',
    'version': '19.0.1.0.0',
    'author': "Webkul Software Pvt. Ltd.",
    'license': 'OPL-1',
    'website': 'https://store.webkul.com',
    'description': """Odoo Tally Connector
    Tally connector
    Tally 
    Tally accounts""",
    'live_test_url': 'https://www.youtube.com/watch?v=cul14Z9zQGo&ab_channel=Webkul',
    'depends': ['base', 'account', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_view.xml',
        'views/invoice_view.xml',
        'views/tally_export_view.xml',
        'views/tally_field_mapping.xml',
        'views/sequence.xml',
        'data/demo.xml',
    ],
    "images":  ['static/description/Banner.gif'],
    "application": True,
    "installable": True,
    "auto_install": False,
}
