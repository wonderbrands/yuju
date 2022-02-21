# -*- coding: utf-8 -*-
# File:           res_partner.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-07-19

from odoo import models, api, fields
from odoo import exceptions

from ..responses import results
from ..log.logger import logger

from collections import defaultdict
import math
import json

from ..notifier import notifier

class ProductProduct(models.Model):
    _inherit = "product.product"

    id_product_madkting = fields.Char('Id product madkting', size=50)
    last_webhook_madkting = fields.Text('Last Webhook Madkting', default="")

    _sql_constraints = [('id_product_madkting_uniq', 'unique (id_product_madkting,active)',
                         'The relationship between products of madkting and odoo must be one to one!')]

    __update_product_fields = {'name': str,
                               'default_code': str,
                               'type': str,  # 'product', 'service', 'consu'
                               'description': str,
                               'description_purchase': str,
                               'description_sale': str,
                               'list_price': (int, float),
                               'company_id': int,
                               'description_picking': str,
                               'description_pickingout': str,
                               'description_pickingin': str,
                               'image': str,
                               'category_id': int,
                               'taxes': list,
                               'standard_price': (float, int),
                               'weight': (float, int),
                               'weight_unit': str,
                               'barcode': str,
                               'id_product_madkting': (int, str)}

    __update_variation_fields = {'default_code': str,
                                 'company_id': int,
                                 'standard_price': (float, int),
                                 'attributes': dict,
                                 'id_product_madkting': (int, str)}

    @api.model
    def send_webhook(self, product_id):
        """
        :param product_id:
        :type product_id: int
        :return:
        :rtype: dict
        """
        logger.debug("###Send Webhook")
        logger.debug(product_id)
        logger.debug(type(product_id))
        product_ids = self.search([('id','=',product_id)], limit=1)
        logger.debug(product_ids)
        if not product_ids:
            return results.error_result('product_not_found',
                                        'product_id not found')
        try:
            logger.debug("###Try to send Webhook")
            notifier.send_stock_webhook(self.env, product_id)
            logger.debug("###Webhook enviado...")
        except Exception as ex:
            logger.debug("###Exception Ocurred on Sending Webhook")
            logger.debug(ex)
            logger.exception(ex)

        if product_ids and product_ids[0].last_webhook_madkting:

            res = json.loads(product_ids[0].last_webhook_madkting)
            return results.success_result(res)
            
        return results.success_result()

    @api.model
    def get_last_webhook(self, product_id):
        """
        :param product_data:
        :type product_data: dict
        :product_data: {
            "product_id" : 1
        }
        :return:
        :rtype: dict
        """
        logger.debug(" ### Last webhook ###")
        product_ids = self.env['product.product'].search([('id', '=', product_id)], limit=1)
        if product_ids and product_ids[0].last_webhook_madkting:
            logger.debug(product_ids[0].last_webhook_madkting)
            res = json.loads(product_ids[0].last_webhook_madkting)
            return results.success_result(res)

        return results.success_result()

    @api.model
    def update_product(self, product_data, product_type):
        """
        :param product_data:
        :type product_data: dict
        :param product_type: type of the product being updated: 'product' or 'variation'
        :type product_type: str
        :return:
        :rtype: dict
        """
        product_id = product_data.pop('id', None)
        if not product_id:
            return results.error_result('missing_product_id',
                                        'product_id is required')

        product = self.with_context(active_test=False) \
                      .search([('id', '=', product_id)])
        if not product:
            return results.error_result('product_not_found',
                                        'The product you are looking for does not exists in odoo or has been deleted')
        fields_validation = self.__validate_update_fields(fields=product_data,
                                                          product_type=product_type)
        if not fields_validation['success']:
            return fields_validation
        try:
            product.write(fields_validation['data'])
        except exceptions.AccessError as ae:
            logger.exception(ae)
            return results.error_result('access_error', ae)
        except Exception as ex:
            logger.exception(ex)
            return results.error_result('save_product_update_exception', ex)
        else:
            return results.success_result()

    @api.model
    def create_variation(self, variation_data):
        """
        :param variation_data:
        {
            'product_id': int, # parent product id
            'default_code': str,
            'company_id': int,
            'standard_price': float,
            'attributes': { # example variation attributes
                'color': 'blue',
                'size': 'S'
            }
        }
        :type variation_data: dict
        :return:
        :rtype: dict
        """
        parent_id = variation_data.pop('product_id', None)
        if not parent_id:
            return results.error_result('missing_product_id',
                                        'product_id is required')

        parent = self.search([('id', '=', parent_id)])
        if not parent:
            return results.error_result(
                'product_not_found',
                'Cannot find the parent product for this variation'
            )

        fields_validation = self.__validate_update_fields(variation_data,
                                                          'variation')
        if not fields_validation['success']:
            return fields_validation

        attributes_structure = parent.attribute_lines_structure()
        variant_attributes = fields_validation['data'].pop('attributes')
        invalid_attributes = list()
        attribute_values = set()

        for attribute, value in variant_attributes.items():
            attribute_values.add(value)
            if attribute not in attributes_structure:
                invalid_attributes.append(attribute)

        if invalid_attributes:
            return results.error_result(
                'invalid_variation_structure',
                '{} doesn\'t match variation structure'.format(', '.join(invalid_attributes))
            )

        current_variations_set = parent.get_variation_sets()
        if attribute_values in current_variations_set:
            return results.error_result(
                'variation_already_exists',
                'The variation with values: {}. already exists for this product.'.format(', '.join(attribute_values))
            )
        # get variation value code
        new_variation_values_ids = list()
        for attribute, value in variant_attributes.items():
            value_id = attributes_structure[attribute].get(value)
            # if this value_id is not already assigned to this attribute line
            if not value_id:
                # try to get value from the existing attribute
                attribute_id = attributes_structure[attribute]['attribute_id']
                attribute_val = self.env['product.attribute.value'] \
                                    .search([('attribute_id', '=', attribute_id), ('name', '=', value)],
                                            limit=1)
                if not attribute_val:
                    # if the attribute value doesn't exists yet create it
                    try:
                        attribute_val = self.env['product.attribute.value'].create(
                            {'name': value, 'attribute_id': attribute_id}
                        )
                    except Exception as ex:
                        logger.exception(ex)
                        return results.error_result(
                            'create_variation_attribute_value_error',
                            str(ex)
                        )
                    else:
                        template_attribute_line_id = attributes_structure[attribute]['attribute_line_id']
                        attribute_line = self.env['product.template.attribute.line'].browse(template_attribute_line_id)
                        try:
                            # add new value to product template attribute line
                            attribute_line.value_ids = [(4, attribute_val.id)]
                        except Exception as ex:
                            logger.exception(ex)
                # add new value to product template attribute line
                try:
                    self.env['product.template.attribute.value'].create({
                        'product_attribute_value_id': attribute_val.id,
                        'product_tmpl_id': parent.product_tmpl_id.id
                    })
                except Exception as ex:
                    logger.exception(ex)
                    return results.error_result(
                        'template_attribute_line_create_error', str(ex)
                    )
                value_id = attribute_val.id
            new_variation_values_ids.append(value_id)
        try:
            new_variation = self.create({
                'product_tmpl_id': parent.product_tmpl_id.id,
                'attribute_value_ids': [(6, 0, new_variation_values_ids)]
            })
        except Exception as ex:
            logger.exception(ex)
            return results.error_result('variation_create_error', str(ex))
        else:
            new_variation.write(fields_validation['data'])
            new_variation_data = new_variation.copy_data()[0]
            new_variation_data['id'] = new_variation.id
            new_variation_data['product_id'] = parent.id
            new_variation_data['attributes'] = variant_attributes
            return results.success_result(new_variation_data)

    @api.model
    def get_product(self, product_id, only_active=False):
        """
        :param only_active:
        :type only_active: bool
        :param product_id:
        :type product_id: int
        :return:
        :rtype: dict
        """
        product = self.with_context(active_test=only_active) \
                      .search([('id', '=', product_id)], limit=1)

        if not product:
            return results.error_result(
                'product_not_found',
                'The product that you are trying to get doesn\'t exists or has been deleted'
            )
        return results.success_result(product.get_data_with_variations())

    @api.model
    def get_variation(self, product_id, only_active=False):
        """
        :param only_active:
        :type only_active: bool
        :param product_id:
        :type product_id: int
        :return:
        :rtype: dict
        """
        product = self.with_context(active_test=only_active) \
                      .search([('id', '=', product_id)], limit=1)

        if not product:
            return results.error_result(
                'product_not_found',
                'The product that you are trying to deactivate doesn\'t exists or has been deleted'
            )
        return results.success_result(product.get_data())

    @api.model
    def get_product_list(self, elements_per_page=50, page=1):
        """
        :param elements_per_page: max 300
        :type elements_per_page: int
        :param page:
        :type page: int
        :return:
        :rtype: dict
        """
        if elements_per_page > 300:
            elements_per_page = 300

        if page < 1:
            page = 1

        products_total = self.search_count([])
        offset = elements_per_page * (page - 1)
        products = self.search([],
                               limit=elements_per_page,
                               offset=offset,
                               order='id asc')
        product_list = {
            'page_count': math.ceil(products_total / elements_per_page),
            'page': page,
            'products_total': products_total,
            'products': []
        }

        for product in products:
            product_list['products'].append({
                'id': product.id,
                'product_id': product.product_variant_id.id,
                'default_code': product.default_code,
                'categ_id': product.categ_id.id,
                'categ_name': product.categ_id.name
            })
        return results.success_result(product_list)

    @api.model
    def product_count(self):
        """
        :return:
        """
        return results.success_result(self.search_count([]))

    @api.model
    def deindex_products(self, product_ids):
        """
        :param product_ids:
        :type product_ids: list
        :return:
        """
        try:
            if product_ids[0] == '*':
                self.search([]).write({'id_product_madkting': None})
            else:
                self.search([('id', 'in', product_ids)]) \
                    .write({'id_product_madkting': None})
        except Exception as ex:
            logger.exception(ex)
            results.error_result('deindex_write_exception', str(ex))
        else:
            return results.success_result()

    def get_data(self):
        """
        :rtype: dict
        :return:
        """
        self.ensure_one()
        data = self.copy_data()[0]
        data['id'] = self.id
        data['product_id'] = self.product_variant_id.id
        data['template_id'] = self.product_tmpl_id.id
        data['attributes'] = dict()
        for attribute_value in self.attribute_value_ids:
            attribute_name = attribute_value.attribute_id.name
            data['attributes'][attribute_name] = attribute_value.name
        return data

    def get_data_with_variations(self):
        """
        :rtype: dict
        :return:
        """
        self.ensure_one()
        data = self.product_tmpl_id.copy_data()[0]
        data['variations'] = list()
        variation_attributes = defaultdict(list)
        data['template_id'] = self.product_tmpl_id.id
        data['id'] = self.product_variant_id.id
        data['default_code'] = self.product_variant_id.default_code
        data['product_variant_count'] = self.product_tmpl_id.product_variant_count
        for variation in self.product_variant_ids:
            variation_data = variation.get_data()
            for attribute, value in variation_data['attributes'].items():
                if value not in variation_attributes[attribute]:
                    variation_attributes[attribute].append(value)
            data['variations'].append(variation_data)
        data['variation_attributes'] = dict(variation_attributes)
        return data

    def __validate_update_fields(self, fields, product_type):
        """
        :param fields:
        :param product_type:
        :return: results dict with updatable fields filtered and fields analysis results
        :rtype: dict
        """
        invalid_types = list()
        filtered_fields = dict()

        if product_type == 'product':
            updatable_fields = self.__update_product_fields
        else:
            updatable_fields = self.__update_variation_fields

        for field, value in fields.items():
            if field in updatable_fields:
                field_type = updatable_fields[field]
                if not isinstance(value, field_type):
                    invalid_types.append(field)
                else:
                    filtered_fields[field] = value

        if not fields:
            return results.error_result('nothing_to_update')

        if invalid_types:
            return results.error_result('invalid_field_type',
                                        ', '.join(invalid_types))
        return results.success_result(filtered_fields)

    def attribute_lines_structure(self):
        """
        :return: dictionary with attribute lines structure
        {
          'attribute name': {
            'attribute_id': int,
            'values': {
              'value name': value id,
              'value name': value id,
              ...
            },
            ...
          }
        :rtype: dict
        """
        self.ensure_one()
        structure = defaultdict(dict)
        for attribute_line in self.attribute_line_ids:
            attribute_name = attribute_line.attribute_id.name
            structure[attribute_name]['attribute_line_id'] = attribute_line.id
            structure[attribute_name]['attribute_id'] = attribute_line.attribute_id.id
            structure[attribute_name]['values'] = dict()
            for value in attribute_line.value_ids:
                structure[attribute_name]['values'][value.name] = value.id
        return dict(structure)

    def get_variation_sets(self):
        """
        :return: list of variations in sets
        :rtype: list
        """
        self.ensure_one()
        variants = list()
        for variation in self.product_variant_ids:
            values = set()
            for value in variation.attribute_value_ids:
                values.add(value.name)
            if values:
                variants.append(values)
        return variants

    def get_stock_by_location(self):
        """
        Returns the stock by location, only active locations of type internal
        :return:
        :rtype: dict
        """
        self.ensure_one()
        quantities = dict()
        locations = self.env['stock.location'] \
                        .search([('active', '=', True),
                                 ('usage', '=', 'internal')])
        for location in locations:
            quantities[location.id] = self.with_context({'location': location.id}) \
                                          .qty_available
        return quantities
