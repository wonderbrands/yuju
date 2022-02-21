# -*- coding: utf-8 -*-
# File:           product_template.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-04-17

from odoo import models, api
from odoo import exceptions
from collections import defaultdict
from ..log.logger import logger
from ..responses import results
import psycopg2


class ProductTemplate(models.Model):

    _inherit = 'product.template'

    @api.model
    def mdk_create(self, product_data):
        """
        TODO: Prices are defined by product not variant. This behavior may be emulated with discount rules in odoo
              at this moment there is only price definition by product
        :param product_data:
        {
            'name': str,
            'default_code': str, # sku
            'type': str, # 'product', 'service', 'consu'
            'description': str,
            'description_purchase': str,
            'description_sale': str,
            'list_price': float,
            'company_id': int,
            'description_picking': str,
            'description_pickingout': str,
            'description_pickingin': str,
            'image': str, # base64 string
            'category_id': int,
            'taxes': list, # list of int
            'cost': float,
            'weight': float, # only if is parente product
            'weight_unit': str,
            'barcode': str, # only if is parent product
            'initial_stock': int, # TODO: implement initial stock functionality
            'variation_attributes': {
                'color':['blue', 'black'], # example variation
                'size': ['S', 'L'] # example variation
            }, # dict with variation as key and values in a list
            'variations': [
                {
                    'default_code': str,
                    'company_id': int,
                    'barcode': str,
                    'weight': float,
                    'cost': float,
                    'initial_stock': int, # TODO: implement initial stock functionality
                    'attributes': { # TODO: return this part of the structure
                        'color': 'blue',
                        'size': 'S'
                    }
                }
            ]
        }
        :type product_data: dict
        :return:
        :rtype: dict
        """
        variation_attributes = product_data.pop('variation_attributes', None)
        variations = product_data.pop('variations', None)
        has_variations = True if variation_attributes else False
        taxes = product_data.pop('taxes', None)
        cost = product_data.pop('cost', None)
        weight_unit = product_data.pop('weight_unit', None)
        # stock = product_data.pop('initial_stock', None)
        if taxes:
            taxes_id = self.env['account.tax'] \
                           .get_sale_taxes_ids(product_data['company_id'], taxes)
            product_data['taxes_id'] = taxes_id

        if weight_unit:
            weight_uom = self.env['uom.uom'].get_uom_by_name(weight_unit)
            product_data['weight_uom_id'] = weight_uom

        product_data['standard_price'] = cost

        # create a product simple
        if not has_variations:
            try:
                new_product_simple = self.env['product.product'].create(product_data)
            except Exception as ex:
                logger.exception(ex)
                return results.error_result(code='product_create_error',
                                            description='Product couldn\'t be created because '
                                                        'of the following exception: {}'.format(ex))
            else:
                # if stock:
                #    pass # TODO: implement initial stock functionality
                return results.success_result(data=new_product_simple.get_data_with_variations())

        # create product with variations
        # validate variations
        product_template_attribute_lines = list()
        attribute_value_ids = dict()

        for attribute_name, values in variation_attributes.items():
            attribute_line = dict()
            attribute = self.env['product.attribute'].search([('name', '=', attribute_name)], limit=1)
            if not attribute:
                try:
                    # create attribute
                    attribute = self.env['product.attribute'].create({'name': attribute_name,
                                                                      'create_variant': 'always',
                                                                      'type': 'select'})
                    # create new attribute values
                    self.env['product.attribute.value'].create(
                        [{'name': val, 'attribute_id': attribute.id} for val in values]
                    )
                except Exception as ex:
                    logger.exception(ex)
                    return results.error_result(code='create_variation_attribute_error',
                                                description='Product couldn\'t be created because '
                                                            'of the following exception: {}'.format(ex))
            else:
                current_attribute_values = {val.name: val.id for val in attribute.value_ids}
                _has_new_values_created = False
                for value in values:
                    if value not in current_attribute_values:
                        try:
                            new_att_val = self.env['product.attribute.value'].create({'name': value,
                                                                                      'attribute_id': attribute.id})
                        except Exception as ex:
                            logger.exception(ex)
                            return results.error_result(code='create_variation_attribute_value_error',
                                                        description='Product couldn\'t be created because '
                                                                    'of the following exception: {}'.format(ex))
                        else:
                            _has_new_values_created = True
                            current_attribute_values[new_att_val.name] = new_att_val.id
                if _has_new_values_created:
                    # if new values has been created for this attribute
                    # invalidate the cache in order to get value_ids updated
                    attribute.invalidate_cache()

            # assign attribute lines for product creation
            attribute_value_ids[attribute.name] = {
                value.name: value.id for value in attribute.value_ids if value.name in values
            }
            attribute_line['attribute_id'] = attribute.id
            attribute_line['value_ids'] = [(6, 0, [val.id for val in attribute.value_ids if val.name in values])]
            product_template_attribute_lines.append(attribute_line)

        try:
            new_template = self.create(product_data)
        except Exception as ex:
            logger.exception(ex)
            return results.error_result(code='product_template_create_error',
                                        description='Product couldn\'t be created because '
                                                    'of the following exception: {}'.format(ex))
        for line in product_template_attribute_lines:
            line['product_tmpl_id'] = new_template.id

        try:
            self.env['product.template.attribute.line'].create(product_template_attribute_lines)
        except Exception as ex:
            logger.exception(ex)
            return results.error_result('template_attribute_line_create_error',
                                        'Error creating lines {}'.format(ex))
        # create variations
        for variation in variations:
            value_ids = list()
            # variation_stock = variation.pop('initial_stock', None)
            variation['standard_price'] = variation.pop('cost', None)
            for variation_att in variation_attributes:
                value = variation.pop(variation_att)
                value_ids.append(attribute_value_ids[variation_att][value])
            logger.info(value_ids)
            try:
                new_variation = self.env['product.product'].create({
                    'product_tmpl_id': new_template.id,
                    'attribute_value_ids': [(6, 0, value_ids)]
                })
            except Exception as ex:
                logger.exception(ex)
                new_template.unlink()
                return results.error_result('variation_create_error', str(ex))
            else:
                new_variation.write(variation)
                # if variation_stock:
                #    pass # TODO: implement initial stock functionality
        new_product_data = new_template.product_variant_id \
                                       .get_data_with_variations()
        return results.success_result(new_product_data)

    def change_product_status(self, template_id, active):
        """
        :param template_id:
        :type template_id: int
        :param active:
        :type active: bool
        :return:
        :rtype: dict
        """
        product = self.with_context(active_test=False) \
                      .search([('id', '=', template_id)], limit=1)
        if not product:
            return results.error_result(
                'product_not_found',
                'The product that you are trying to change doesn\'t exists or has been deleted'
            )
        try:
            product.active = active
        except Exception as ex:
            logger.exception(ex)
            return results.error_result('activate_product_error', str(ex))
        else:
            return results.success_result(
                product.product_variant_id.get_data_with_variations()
            )

    @api.model
    def deactivate_product(self, template_id):
        """
        :param template_id:
        :type template_id: int
        :return:
        """
        """
        variant deactivation may bring adverse results,
        you should validate the default odoo behavior before allow this functionality
        """
        return self.change_product_status(template_id, active=False)

    @api.model
    def activate_product(self, template_id):
        """
        :param template_id:
        :type template_id: int
        :return:
        """
        return self.change_product_status(template_id, active=True)

    @api.model
    def delete_product(self, template_id):
        """
        :param template_id:
        :type template_id: int
        :rtype: dict
        :return:
        """
        product = self.with_context(active_test=False) \
                      .search([('id', '=', template_id)])
        if not product:
            return results.error_result(
                'product_not_found',
                'The product that you are trying to delete doesn\'t exists or is deleted already'
            )
        try:
            product.unlink()
        except (exceptions.ValidationError, psycopg2.IntegrityError) as ve:
            logger.exception(ve)
            return results.error_result(
                'related_with_sales',
                'The product cannot be deleted because is related with sale orders'
            )
        except Exception as ex:
            logger.exception(ex)
            return results.error_result('delete_product_exception', str(ex))
        else:
            return results.success_result()
