# -*- coding: utf-8 -*-
# File:           res_partner.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-03-20
from odoo import models, api
from odoo import exceptions
from ..responses import results


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def create_customer(self, customer_data):
        """
        :type customer_data: dict
        :param customer_data: dictionary with customer data
        {
            'name': str,
            'tz': str, #'America/Mexico_City',
            'vat': str, # tax_id
            'comment': str,
            'function': str,
            'street': str,
            'street2': str,
            'zip': str,
            'city': str,
            'country_code': str, # MX
            'email': str,
            'phone': str,
            'mobile': str,
            'company_id': int,
            'company_name': str
            'billing_address': {
                'name': str,
                'tz': str, #'America/Mexico_City',
                'vat': str, # tax_id
                'comment': str,
                'function': str,
                'street': str,
                'street2': str,
                'zip': str,
                'city': str,
                'country_code': str,
                'email': str,
                'phone': str,
                'mobile': str,
                'company_id': int,
                'company_name': str
            },
            'shipping_address': {
                'name': str,
                'tz': str, #'America/Mexico_City',
                'vat': str, # tax_id
                'comment': str,
                'function': str,
                'street': str,
                'street2': str,
                'zip': str,
                'city': str,
                'country_code': str,
                'email': str,
                'phone': str,
                'mobile': str,
                'company_id': int,
                'company_name': str
            }
        }
        :return:
        """
        defaults = {
            'active': True,
            'customer': True,
            'supplier': False,
            'employee': False,
            'image': None,
            'image_medium': None,
            'image_small': None,
            'partner_gid': 0,
            'is_company': False,
            'industry_id': False,
            'color': 0,
        }
        customer_data.update(defaults)
        partners = {
            'delivery': customer_data.pop('billing_address', dict()),
            'invoice': customer_data.pop('shipping_address', dict())
        }

        try:
            country_code = customer_data.pop('country_code', None)
            customer_data['country_id'] = self._get_country_id(country_code)
            new_customer = self.create(customer_data)
        except exceptions.AccessError as err:
            return results.error_result(
                code='access_error',
                description=str(err)
            )
        except Exception as ex:
            return results.error_result(
                code='create_costumer_error',
                description='Error trying to create new costumer: {}'.format(ex)
            )
        warnings = list()
        for type_, partner in partners.items():
            if not partner:
                continue
            r = self.add_address(customer_id=new_customer.id,
                                 type_=type_,
                                 address=partner)

            if not r['success']:
                warnings.extend(r['errors'])
        remove_fields = ['image', 'image_medium', 'image_small']
        new_customer_data = new_customer.copy_data()[0]
        new_customer_data['id'] = new_customer.id
        for field in remove_fields:
            new_customer_data.pop(field)
        return results.success_result(data=new_customer_data, warnings=warnings)

    @api.model
    def add_address(self, customer_id, type_, address):
        """
        :param customer_id:
        :type customer_id:int
        :param type_: delivery or invoice
        :type type_: str
        :param address:
        :type address: dict
        :return:
        """
        country_code = address.pop('country_code', None)
        defaults = {
            'active': True,
            'customer': True,
            'supplier': False,
            'employee': False,
            'image': None,
            'image_medium': None,
            'image_small': None,
            'partner_gid': 0,
            'is_company': False,
            'industry_id': False,
            'color': 0,
            'type': type_,
            'parent_id': customer_id,
            'country_id': self._get_country_id(country_code)
        }
        address.update(defaults)
        try:
            new_address = self.create(address)
        except exceptions.AccessError as err:
            return results.error_result(
                code='access_error',
                description=str(err)
            )
        except Exception as ex:
            return results.error_result(
                code='create_costumer_error',
                description='Error trying to create new costumer: {}'.format(ex)
            )
        else:
            data = {'id': new_address.id}
            return results.success_result(data=data)

    def _get_country_id(self, country_code):
        """
        :param country_code:
        :type country_code: str
        :return: int | None
        """
        country = self.env['res.country'].search([('code', '=', country_code)])
        if not country:
            return
        elif len(country) != 1:
            return
        else:
            return country.id
