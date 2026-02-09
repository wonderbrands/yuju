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
import logging as _logger
_logger = _logger.getLogger(__name__)


class ProductTemplate(models.Model):

    _inherit = 'product.template'

    @api.model
    def update_mapping_fields(self, product_data):
        product_data = self.env['yuju.mapping.field'].get_field_mappings(product_data, 'product.template')
        return product_data

    @api.model
    def mdk_create(self, product_data, id_shop=None):
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
                    'color': 'blue',
                    'size': 'S'
                }
            ]
        }
        :type product_data: dict
        :return:
        :rtype: dict
        """
        logger.info("### MDK CREATE PRODUCT DATA ###")
        logger.info(product_data)
        config = self.env['madkting.config'].get_config()
        products = self.env['product.product']

        if config and config.simple_description_enabled:
            try:
                product_data.pop('description_sale')
                product_data.pop('description_purchase')
                product_data.pop('description_picking')
                product_data.pop('description_pickingout')
                product_data.pop('description_pickingin')
            except Exception as e:
                logger.debug(e)
                pass

        company_id = product_data.get('company_id', False)
        variation_attributes = product_data.pop('variation_attributes', None)
        variations = product_data.pop('variations', [])
        has_variations = True if variation_attributes else False
        taxes = product_data.pop('taxes', None)
        weight_unit = product_data.pop('weight_unit', None)
        if 'image' in product_data:
            product_data['image_1920'] = product_data.pop('image', None)
        # stock = product_data.pop('initial_stock', None)
        if taxes:
            taxes_id = self.env['account.tax'] \
                           .get_sale_taxes_ids(product_data['company_id'], taxes)
            product_data['taxes_id'] = taxes_id

        if weight_unit:
            weight_uom = self.env['uom.uom'].get_uom_by_name(weight_unit)
            product_data['weight_uom_name'] = weight_uom.name

        if product_data.get('cost'):
            product_data['standard_price'] = product_data.pop('cost', None)

        supplier_data = False
        if product_data.get('provider'):
            supplier_data = product_data.pop('provider', None)

        logger.debug("### SEARCH BARCODE : {} ###".format(product_data.get('barcode')))
        if 'barcode' in product_data:
            barcode = product_data.get('barcode')
            if barcode:
                
                product_ids = self.env['product.product'].with_context(active_test=False).search([('barcode', '=', barcode)])
                if product_ids.ids:
                    logger.warning(f'El codigo de barras ya esta previamente registrado {barcode}')

                    if config and config.validate_barcode_exists:               
                        return results.error_result(code='duplicated_barcode',
                                                description='El codigo de barras ya esta previamente registrado')
                    else:
                        product_data.pop('barcode')
            else:
                logger.debug("## DROP EMPTY BARCODE ##")
                product_data.pop('barcode')

        if 'type' in product_data and product_data['type'] == 'product':
            product_data['type'] = 'consu'
            product_data['is_storable'] = True

        if 'detailed_type' in product_data:
            product_data.pop('detailed_type')

        product_data = self.update_mapping_fields(product_data)

        # create a product simple
        if not has_variations:
            logger.info("#CREATE PRODUCT SIMPLE")
            logger.info(product_data)
            
            try:
                new_product_simple = self.env['product.product'].create(product_data)
            except Exception as ex:
                logger.exception(ex)
                return results.error_result(code='product_create_error',
                                            description='Product couldn\'t be created because '
                                                        'of the following exception: {}'.format(ex))
            else:
                if supplier_data:
                    new_product_simple._create_supplier_product(supplier_data)

                return results.success_result(data=new_product_simple.get_data_with_variations())

        # create product with variations
        # validate variations
        product_template_attribute_lines = []

        logger.info("#CREATE PRODUCT WITH VARIATIONS")
        logger.info(variation_attributes)

        for attribute_name, values in variation_attributes.items():
            attribute_line = dict()
            _logger.info("Processing attribute: {} with values: {}".format(attribute_name, values))
            attribute = self.env['product.attribute'].search([('name', '=', attribute_name)], limit=1)            
            if not attribute:
                try:
                    # create attribute
                    _logger.info("Attribute {} not found, creating...".format(attribute_name))
                    attribute = self.env['product.attribute'].create({'name': attribute_name,
                                                                      'create_variant': 'always'})
                    # create new attribute values
                    _logger.info("Creating attribute values {} for attribute {}".format(values, attribute_name))
                    self.env['product.attribute.value'].create(
                        [{'name': val, 'attribute_id': attribute.id} for val in values]
                    )
                except Exception as ex:
                    logger.exception(ex)
                    return results.error_result(code='create_variation_attribute_error',
                                                description='Product couldn\'t be created because '
                                                            'of the following exception: {}'.format(ex))
                else:
                    _logger.info("Attribute {} and its values created.".format(attribute_name))
            else:
                _logger.info("Attribute {} found.".format(attribute_name))
                current_attribute_values = {val.name: val.id for val in attribute.value_ids}
                _logger.info("Current attribute values: {}".format(current_attribute_values))
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
                # if _has_new_values_created:
                    # if new values has been created for this attribute
                    # invalidate the cache in order to get value_ids updated
                    # attribute.invalidate_cache()

            attribute = self.env['product.attribute'].browse(attribute.id)
            attribute_value_ids = []
            attribute_values_updated = {val.name: val.id for val in attribute.value_ids}
            for value in values:
                if value in attribute_values_updated:
                    attribute_value_ids.append(attribute_values_updated[value])
            _logger.info("Final attribute values: {}".format(attribute_value_ids))
            
            attribute_line = {
                'attribute_id': attribute.id,
                'value_ids': [
                    (4, val_id) for val_id in attribute_value_ids
                    # (4, val.id) for val in attribute.value_ids if val.name in values
                ]
            }
            _logger.info("Appending attribute line: {}".format(attribute_line))
            product_template_attribute_lines.append((0, 0, attribute_line))

        product_data['attribute_line_ids'] = product_template_attribute_lines
        product_data.pop('id_product_madkting', None)

        logger.debug("#### VER VARIANTES")
        logger.debug(product_data)
        logger.debug(id_shop)
        
        if id_shop:
            new_template = None            
            sku_product = product_data.get('default_code')
            product_ids = products.search([('default_code', '=', sku_product)], limit=1)
            if product_ids:
                new_template = product_ids.product_templ_id
            else:
                for var in variations:
                    sku_product = var.get('default_code')
                    product_ids = products.search([('default_code', '=', sku_product)], limit=1)
                    if product_ids:
                        new_template = product_ids.product_tmpl_id
                        break

            if not new_template:
                try:
                    new_template = self.create(product_data)
                except Exception as ex:
                    logger.exception(ex)
                    return results.error_result(code='product_template_create_error',
                                                description='Product couldn\'t be created because '
                                                            'of the following exception: {}'.format(ex))
        else:
            try:
                new_template = self.create(product_data)
            except Exception as ex:
                logger.exception(ex)
                return results.error_result(code='product_template_create_error',
                                            description='Product couldn\'t be created because '
                                                        'of the following exception: {}'.format(ex))
        
        for product_variant in new_template.product_variant_ids:
            data = product_variant.get_data()

            variation_data = None
            for v in range(len(variations)):
                if all(attrib in variations[v] and variations[v][attrib] == value for attrib, value in data.get('attributes').items() ):
                    variation_data = variations.pop(v)
                    break
            # logger.debug("## VARIATION DATA ##")
            # logger.debug(variation_data)
            if variation_data:
                # logger.debug("Entra..")

                if 'type' in variation_data and variation_data['type'] == 'product':
                    variation_data['type'] = 'consu'

                if variation_data.get('cost'):
                    variation_data['standard_price'] = variation_data.pop('cost', None)

                if 'image' in variation_data:
                    variation_data['image_1920'] = variation_data.pop('image', None)

                if supplier_data:
                    product_variant._create_supplier_product(supplier_data)

                for attrib in data.get('attributes'):
                    variation_data.pop(attrib)

                variation_data.pop('attributes', None)
                variation_data.pop('product_id', None)
                variation_data.pop('id', None)
                
                # logger.debug("## VARIATION DATA ##")
                # logger.debug(variation_data)
                product_variant.write(variation_data)

        return results.success_result(new_template.product_variant_id.get_data_with_variations())

    def change_product_status(self, template_id, active, id_shop=None):
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
    def deactivate_product(self, template_id, id_shop=None):
        """
        :param template_id:
        :type template_id: int
        :return:
        """
        """
        variant deactivation may bring adverse results,
        you should validate the default odoo behavior before allow this functionality
        """
        return self.change_product_status(template_id, active=False, id_shop=id_shop)

    @api.model
    def activate_product(self, template_id, id_shop=None):
        """
        :param template_id:
        :type template_id: int
        :return:
        """
        return self.change_product_status(template_id, active=True, id_shop=id_shop)

    @api.model
    def delete_product(self, template_id, id_shop=None):
        """
        :param template_id:
        :type template_id: int
        :rtype: dict
        :return:
        """
        producto_encontrado = True
        product = self.search([('id', '=', template_id)])
        if not product:
            logger.debug("Producto no encontrado, se busca archivado.")
            producto_encontrado = False
            product = self.with_context(active_test=False).search([('id', '=', template_id)])

            if not product:
                logger.debug("Finaliza eliminacion")
                return results.success_result()

        delete_template = True

        if not producto_encontrado:
            logger.debug("Finaliza eliminacion")
            return results.success_result()

        if delete_template:
            try:
                logger.debug("Se elimina el producto")
                for variant in product.product_variant_ids:
                    variant.id_product_madkting = None
                    # variant.barcode = None
                product.active = False
                # product.barcode = None
                product.write({"active": False})
                # product.unlink()
            except (exceptions.ValidationError, psycopg2.IntegrityError) as ve:
                logger.error("Exception IntegrityError")
                logger.exception(ve)
                self.env.cr.rollback()
                return results.error_result(
                    'related_with_sales',
                    'The product cannot be deleted because is related with sale orders'
                )
            except Exception as ex:
                logger.exception("Exception")
                logger.exception(ex)
                self.env.cr.rollback()
                return results.error_result('delete_product_exception', str(ex))

        logger.debug("Finaliza eliminacion")
        return results.success_result()

    def write(self, values):
        res = super(ProductTemplate, self).write(values)
        # Check if we need to update price for products
        need_update = False
        config_ids = self.env['madkting.config'].search([])
        for config in config_ids:
            if config.webhook_price_enabled:
                need_update = True
                break
        if not need_update:
            # logger.debug("No need to update price for products.")
            return res
        for product in self:
            if "list_price" in values:
                products = self.env['product.product'].search([('product_tmpl_id', '=', product.id)])
                for p in products:
                    p.webhook_price_pending = True
        return res