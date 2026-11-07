# # -*- coding: utf-8 -*-
# from odoo import models, api
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class ResPartner(models.Model):
#     _inherit = 'res.partner'
#
#     def _create_portal_user(self):
#         """Create a portal user for this partner if one doesn't exist."""
#         self.ensure_one()
#
#         # Check if user already exists for this partner
#         existing_user = self.env['res.users'].sudo().search([
#             ('partner_id', '=', self.id)
#         ], limit=1)
#
#         if existing_user:
#             _logger.info("User already exists for partner %s (ID: %s)", self.name, self.id)
#             return existing_user
#
#         # Get the portal user group
#         portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
#         if not portal_group:
#             _logger.error("Portal group not found")
#             return False
#
#         # Generate login email if not set
#         login = self.email or f"portal_{self.id}@localhost"
#
#         # Create user values
#         user_vals = {
#             'partner_id': self.id,
#             'login': login,
#             'name': self.name,
#             'email': self.email or login,
#             'groups_id': [(6, 0, [portal_group.id])],
#             'company_id': self.env.company.id,
#             'company_ids': [(6, 0, [self.env.company.id])],
#         }
#
#         try:
#             new_user = self.env['res.users'].sudo().create(user_vals)
#             _logger.info("Created portal user %s for partner %s (ID: %s)", login, self.name, self.id)
#
#             # Send invitation email if email is set
#             if self.email:
#                 new_user.sudo().action_reset_password()
#
#             return new_user
#         except Exception as e:
#             _logger.error("Failed to create portal user for partner %s: %s", self.name, str(e))
#             return False
#
#     @api.model_create_multi
#     def create(self, vals_list):
#         partners = super(ResPartner, self).create(vals_list)
#
#         for partner in partners:
#             # Create portal user if is_broker_partner is True
#             if partner.is_broker_partner:
#                 partner._create_portal_user()
#
#         return partners
#
#     def write(self, vals):
#         result = super(ResPartner, self).write(vals)
#
#         # Check if is_broker_partner was set to True
#         if 'is_broker_partner' in vals and vals['is_broker_partner']:
#             for partner in self:
#                 partner._create_portal_user()
#
#         return result
#
#     def action_create_portal_user(self):
#         """Action to create portal user for broker partners."""
#         for partner in self:
#             if partner.is_broker_partner:
#                 partner._create_portal_user()
#         return True
#
#     @api.model
#     def create_portal_users_for_brokers(self):
#         """Create portal users for all broker partners who don't have users yet."""
#         broker_partners = self.search([('is_broker_partner', '=', True)])
#         created_count = 0
#         for partner in broker_partners:
#             existing_user = self.env['res.users'].sudo().search([
#                 ('partner_id', '=', partner.id)
#             ], limit=1)
#             if not existing_user:
#                 partner._create_portal_user()
#                 created_count += 1
#         _logger.info(f"Created {created_count} portal users for broker partners")
#         return created_count


# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _create_portal_user(self):
        """Create a portal user for this partner only if no user exists at all."""
        self.ensure_one()

        # Agar koi bhi user already exist karta hai (internal ya portal) toh skip karo
        existing_user = self.env['res.users'].sudo().search([
            ('partner_id', '=', self.id)
        ], limit=1)

        if existing_user:
            _logger.info(
                "User already exists for partner %s (ID: %s), type: %s — skipping.",
                self.name, self.id,
                'internal' if existing_user.has_group('base.group_user') else 'portal'
            )
            return existing_user  # Kuch mat karo, chhod do jaise hai

        # Sirf tab portal user banao jab koi user ho hi nahi
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        if not portal_group:
            _logger.error("Portal group not found")
            return False

        login = self.email or f"portal_{self.id}@localhost"

        user_vals = {
            'partner_id': self.id,
            'login': login,
            'name': self.name,
            'email': self.email or login,
            'groups_id': [(6, 0, [portal_group.id])],
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
        }

        try:
            new_user = self.env['res.users'].sudo().create(user_vals)
            _logger.info("Created portal user %s for partner %s (ID: %s)", login, self.name, self.id)

            if self.email:
                new_user.sudo().action_reset_password()

            return new_user
        except Exception as e:
            _logger.error("Failed to create portal user for partner %s: %s", self.name, str(e))
            return False

    @api.model_create_multi
    def create(self, vals_list):
        partners = super(ResPartner, self).create(vals_list)
        # Auto creation band — manually handle karenge
        return partners

    def write(self, vals):
        result = super(ResPartner, self).write(vals)
        # Auto creation band — manually handle karenge
        return result

    def action_create_portal_user(self):
        """Manual action: sirf is_broker_partner=True wale partners ke liye portal user banao."""
        for partner in self:
            if partner.is_broker_partner:
                partner._create_portal_user()
            else:
                _logger.info(
                    "Partner %s is not a broker partner — skipping.", partner.name
                )
        return True

    @api.model
    def create_portal_users_for_brokers(self):
        """Sirf un broker partners ke liye portal user banao jinke paas abhi koi user nahi hai."""
        broker_partners = self.search([('is_broker_partner', '=', True)])
        created_count = 0
        skipped_count = 0

        for partner in broker_partners:
            existing_user = self.env['res.users'].sudo().search([
                ('partner_id', '=', partner.id)
            ], limit=1)

            if existing_user:
                _logger.info(
                    "Skipping partner %s — user already exists (%s).",
                    partner.name, existing_user.login
                )
                skipped_count += 1
                continue

            partner._create_portal_user()
            created_count += 1

        _logger.info(
            "Portal user creation done — Created: %s, Skipped: %s",
            created_count, skipped_count
        )
        return created_count