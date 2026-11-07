# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError


class PortalBroker(CustomerPortal):
    """Portal controller for broker allotment access."""

    def _prepare_home_portal_values(self, counters):
        """Add broker allotment count to portal dashboard."""
        values = super()._prepare_home_portal_values(counters)
        if 'broker_allotment_count' in counters:
            # Use sudo to count records, then filter by partner
            count = request.env['broker.allotment'].sudo().search_count([
                ('partner_id', '=', request.env.user.partner_id.id)
            ])
            values['broker_allotment_count'] = count
        return values

    @http.route(['/my', '/my/home'], type='http', auth="user", website=True)
    def home(self, **kw):
        """Override home to ensure broker allotment count is available."""
        values = self._prepare_portal_layout_values()
        # Always compute the count for the dashboard using sudo with partner filter
        values['broker_allotment_count'] = request.env['broker.allotment'].sudo().search_count([
            ('partner_id', '=', request.env.user.partner_id.id)
        ])
        return request.render("portal.portal_my_home", values)

    def _prepare_broker_allotment_domain(self):
        """Prepare domain for broker allotment search."""
        return [('partner_id', '=', request.env.user.partner_id.id)]

    def _get_broker_allotment_searchbar_sortings(self):
        """Return available sort options for broker allotments."""
        return {
            'date': {'label': _('Newest'), 'order': 'date_order desc'},
            'name': {'label': _('Reference'), 'order': 'name'},
            'state': {'label': _('Status'), 'order': 'state'},
        }

    def _get_broker_allotment_searchbar_filters(self):
        """Return available filter options."""
        return {
            'all': {'label': _('All'), 'domain': []},
            'draft': {'label': _('Draft'), 'domain': [('state', '=', 'draft')]},
            'confirm': {'label': _('Confirmed'), 'domain': [('state', '=', 'confirm')]},
            'cancel': {'label': _('Cancelled'), 'domain': [('state', '=', 'cancel')]},
        }

    @http.route(['/my/broker-allotments', '/my/broker-allotments/page/<int:page>'],
                type='http', auth="user", website=True)
    def portal_my_broker_allotments(self, page=1, date_begin=None, date_end=None,
                                     sortby='date', filterby='all', **kw):
        """List broker allotments for the current portal user."""
        values = self._prepare_portal_layout_values()
        # Use sudo to access broker.allotment records
        BrokerAllotment = request.env['broker.allotment'].sudo()

        domain = self._prepare_broker_allotment_domain()

        # Apply date filters
        if date_begin and date_end:
            domain += [('date_order', '>=', date_begin), ('date_order', '<=', date_end)]

        # Apply state filter
        searchbar_filters = self._get_broker_allotment_searchbar_filters()
        domain += searchbar_filters.get(filterby, searchbar_filters.get('all'))['domain']

        # Sorting
        searchbar_sortings = self._get_broker_allotment_searchbar_sortings()
        order = searchbar_sortings.get(sortby, searchbar_sortings.get('date'))['order']

        # Count for pager (using sudo with partner domain filter)
        allotment_count = BrokerAllotment.search_count(domain)

        # Pager
        pager = portal_pager(
            url="/my/broker-allotments",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=allotment_count,
            page=page,
            step=self._items_per_page
        )

        # Fetch records (using sudo with partner domain filter)
        allotments = BrokerAllotment.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset']
        )

        values.update({
            'date_begin': date_begin,
            'date_end': date_end,
            'allotments': allotments,
            'page_name': 'broker_allotment',
            'pager': pager,
            'default_url': '/my/broker-allotments',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
        })
        return request.render("portal_broker.portal_my_broker_allotments", values)

    @http.route(['/my/broker-allotment/<int:allotment_id>'], type='http', auth="user", website=True)
    def portal_broker_allotment_detail(self, allotment_id, **kw):
        """Show detailed view of a specific broker allotment."""
        # Use sudo to access record, then verify ownership manually
        allotment = request.env['broker.allotment'].sudo().browse(allotment_id)
        if not allotment.exists() or allotment.partner_id.id != request.env.user.partner_id.id:
            raise AccessError(_("You are not authorized to view this record."))

        values = self._prepare_portal_layout_values()
        values.update({
            'allotment': allotment,
            'page_name': 'broker_allotment',
        })
        return request.render("portal_broker.portal_broker_allotment_detail", values)

    @http.route(['/my/broker-allotments/pdf/<int:allotment_id>'], type='http', auth="user", website=True)
    def portal_broker_allotment_report(self, allotment_id, **kw):
        """Generate PDF report for a broker allotment."""
        # Use sudo to access record, then verify ownership manually
        allotment = request.env['broker.allotment'].sudo().browse(allotment_id)
        if not allotment.exists() or allotment.partner_id.id != request.env.user.partner_id.id:
            raise AccessError(_("You are not authorized to access this record."))

        # Generate report
        pdf = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'sale_order_modifier_hmrc.report_broker_allotment',
            [allotment.id]
        )
        pdf_http_headers = [('Content-Type', 'application/pdf'), ('Content-Length', len(pdf[0]))]
        return request.make_response(pdf[0], headers=pdf_http_headers)

    # ==================== PARTY ORDER CREATION ====================

    @http.route(['/my/broker-allotment/<int:allotment_id>/create-party-order'],
                type='http', auth="user", website=True)
    def portal_create_party_order(self, allotment_id, **kw):
        """Show form to create a Party Order from Broker Allotment."""
        # Verify the broker allotment belongs to the current user
        allotment = request.env['broker.allotment'].sudo().browse(allotment_id)
        if not allotment.exists() or allotment.partner_id.id != request.env.user.partner_id.id:
            raise AccessError(_("You are not authorized to access this record."))

        # Check if there are lines with balance qty > 0
        available_lines = allotment.order_line.filtered(lambda l: l.balance_qty > 0)
        if not available_lines:
            return request.redirect('/my/broker-allotment/%d?error=no_balance' % allotment_id)

        # Get parties (customers with is_party_customer=True)
        Party = request.env['res.partner'].sudo()
        parties = Party.search([('is_party_customer', '=', True)], order='name')

        values = self._prepare_portal_layout_values()
        values.update({
            'allotment': allotment,
            'parties': parties,
            'page_name': 'broker_allotment',
            'error': kw.get('error'),
        })
        return request.render("portal_broker.portal_create_party_order", values)

    @http.route(['/my/broker-allotment/<int:allotment_id>/create-party-order/submit'],
                type='http', auth="user", website=True, methods=['POST'])
    def portal_create_party_order_submit(self, allotment_id, **post):
        """Submit Party Order creation form."""
        # Verify the broker allotment belongs to the current user
        allotment = request.env['broker.allotment'].sudo().browse(allotment_id)
        if not allotment.exists() or allotment.partner_id.id != request.env.user.partner_id.id:
            raise AccessError(_("You are not authorized to access this record."))

        # Get form data
        party_id = int(post.get('party_id', 0))
        pay_date = post.get('pay_date')
        lift_date = post.get('lift_date')

        if not party_id:
            return request.redirect('/my/broker-allotment/%d/create-party-order?error=missing_party' % allotment_id)

        # Get party partner
        party = request.env['res.partner'].sudo().browse(party_id)
        if not party.exists():
            return request.redirect('/my/broker-allotment/%d/create-party-order?error=invalid_party' % allotment_id)

        # Get lines data
        lines_to_create = []
        has_valid_line = False

        for line in allotment.order_line.filtered(lambda l: l.balance_qty > 0):
            line_id = str(line.id)
            qty_field = 'line_qty_%d' % line.id
            price_field = 'line_price_%d' % line.id
            selected = post.get('line_selected_%d' % line.id)

            if selected:
                qty = float(post.get(qty_field, 0) or 0)
                price = float(post.get(price_field, 0) or line.price_unit or 0)

                if qty > 0:
                    if qty > line.balance_qty:
                        return request.redirect('/my/broker-allotment/%d/create-party-order?error=qty_exceeded' % allotment_id)
                    if price <= 0:
                        return request.redirect('/my/broker-allotment/%d/create-party-order?error=invalid_price' % allotment_id)

                    has_valid_line = True
                    lines_to_create.append({
                        'product_id': line.product_id.id,
                        'product_uom_qty': qty,
                        'product_uom_id': line.product_uom_id.id,
                        'price_unit': price,
                        'broker_allotment_line_id': line.id,
                        'name': line.product_id.display_name,
                    })

        if not has_valid_line:
            return request.redirect('/my/broker-allotment/%d/create-party-order?error=no_lines' % allotment_id)

        # Create Sale Order
        try:
            SaleOrder = request.env['sale.order'].sudo()
            SaleOrderLine = request.env['sale.order.line'].sudo()

            sale = SaleOrder.create({
                'is_party_sale': True,
                'partner_id': party_id,
                'broker_id': party_id,
                'party_tender_id': allotment.tender_id.id,
                'tender_id': allotment.tender_id.id,
                'pay_date': pay_date,
                'lift_date': lift_date,
                'broker_allotment_id': allotment.id,
                'note': "Party Allotment for Tender %s" % (allotment.tender_id.name or ''),
            })

            # Create order lines
            for line_data in lines_to_create:
                line_data['order_id'] = sale.id
                new_line = SaleOrderLine.create(line_data)
                # Update the broker allotment line
                broker_line = request.env['broker.allotment.line'].sudo().browse(line_data['broker_allotment_line_id'])
                broker_line.party_qty += line_data['product_uom_qty']
                broker_line.balance_qty -= line_data['product_uom_qty']

            return request.redirect('/my/party-order/%d' % sale.id)

        except Exception as e:
            return request.redirect('/my/broker-allotment/%d/create-party-order?error=creation_failed' % allotment_id)

    @http.route(['/my/party-order/<int:order_id>'], type='http', auth="user", website=True)
    def portal_party_order_detail(self, order_id, **kw):
        """Show Party Order detail view."""
        # Use sudo to access record, then verify ownership via broker_allotment
        order = request.env['sale.order'].sudo().browse(order_id)
        if not order.exists():
            raise AccessError(_("Order not found."))

        # Verify the order is linked to a broker allotment belonging to current user
        if order.broker_allotment_id.partner_id.id != request.env.user.partner_id.id:
            raise AccessError(_("You are not authorized to view this order."))

        values = self._prepare_portal_layout_values()
        values.update({
            'order': order,
            'page_name': 'party_order',
        })
        return request.render("portal_broker.portal_party_order_detail", values)
