# -*- coding: utf-8 -*-
# File:           res_partner.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-07-19

from odoo import models, api, fields
from odoo import exceptions
from odoo.exceptions import ValidationError

from ..responses import results
from ..log.logger import logger

from collections import defaultdict
import math

class YujuMapping(models.Model):
    _name = 'yuju.mapping'
    _description = 'Mapeo de Tiendas Yuju'

    company_id = fields.Many2one('res.company', 'Company')
    id_shop_yuju = fields.Char('Id Shop Yuju', size=50)

    _sql_constraints = [
        ('mapping_yuju_unique', 'unique(id_shop_yuju, company_id)', 'El mappeo ya existe')
    ]

    def get_mapping(self, company_id):
        mapping_ids = self.search_count([('company_id', '=', company_id)])
        if mapping_ids == 0:
            return False
        return self.search([('company_id', '=', company_id)])

    @api.model
    def create_mapping(self, mapping):            
        """
        The mapping table is limited to only one record per id_shop, company_id
        :param mapping:
        :type mapping: dict
        :return:
        """
        create_data = []
        mapping_created = []
        for m in mapping:
            company_id = m.get('company_id')
            company_ids = self.env['res.company'].search([('id', '=', int(company_id))], limit=1)
            if not company_ids:
                return results.error_result('The company {} not exists'.format(company_id))
            if not m.get('id_shop'):
                return results.error_result('The id shop is empty for company {}'.format(company_id))

            create_data = {
                "company_id" : company_ids.id,
                "id_shop_yuju" : m.get('id_shop')
            }

            try:
                new_row_id = self.create(create_data)
            except Exception as e:
                return results.error_result('Ocurrio un error al crear el mapeo', str(e))
            else:
                mapping_created.append(new_row_id.id)

        return results.success_result({'mapped_rows' : mapping_created})
       
class ProductYujuMapping(models.Model):
    _name = "yuju.mapping.product"
    _description = 'Mapeo de Productos Yuju'

    product_id = fields.Many2one('product.product', string='Product', ondelete='cascade')
    id_product_yuju = fields.Char('Id Product Yuju', size=50)
    id_shop_yuju = fields.Char('Id Shop Yuju')
    state = fields.Selection([('active', 'Activo'), ('disabled', 'Pausado')], 'Estatus')
    default_code = fields.Char('SKU')
    # company_id = fields.Many2one('res.company', 'Company')
    # barcode = fields.Char('Codigo de Barras')
    
    # _sql_constraints = [('id_product_mapping_uniq', 'unique (product_id, company_id, id_product_yuju, id_shop_yuju)',
    #                      'The relationship between products of yuju and odoo must be one to one!')]

    def create_or_update_product_mapping(self, mapping_data):
        logger.debug("#### CREATE MAPPING ###")
        logger.debug(mapping_data)
        product_id = mapping_data.get('product_id')
        id_shop = mapping_data.get('id_shop_yuju')
        mapping_ids = self.get_product_mapping(product_id, id_shop)
        if mapping_ids:
            try:
                mapping_ids.write(mapping_data)                
            except Exception as err:
                logger.exception(err)
                raise ValidationError('Error al actualizar el mapeo')
        else:
            try:
                self.create(mapping_data)
            except Exception as err:
                logger.exception(err)
                raise ValidationError('Error al crear el mapeo')
        return True

    def get_product_mapping(self, product_id, id_shop):
        logger.debug("#### GET MAPPING ###")
        mapping_ids = []
        count_mapping = self.search_count([('product_id', '=', int(product_id)), ('id_shop_yuju', '=', id_shop)])
        if count_mapping > 0:
            mapping_ids = self.search([('product_id', '=', int(product_id)), ('id_shop_yuju', '=', id_shop)], limit=1)
        logger.debug(mapping_ids)
        return mapping_ids

    def get_product_mapping_by_company(self, product_id, company_id):
        logger.debug("#### GET MAPPING ###")
        # logger.debug(product_id)
        # logger.debug(type(product_id))
        # logger.debug(id_shop)
        # logger.debug(type(id_shop))

        mapping = self.env['yuju.mapping'].get_mapping(company_id)
        if not mapping:
            return False
        
        id_shop = mapping.id_shop_yuju

        mapping_ids = []
        count_mapping = self.search_count([('product_id', '=', int(product_id)), ('id_shop_yuju', '=', id_shop)])
        if count_mapping > 0:
            mapping_ids = self.search([('product_id', '=', int(product_id)), ('id_shop_yuju', '=', id_shop)], limit=1)
        logger.debug(mapping_ids)
        return mapping_ids

    # def get_product_mapping_by_sku(self, sku):
    #     mapping_ids = self.search([('default_code', '=', sku)])
    #     return mapping_ids

    def get_product_mapping_by_product(self, product_id, only_active=False):
        domain = [('product_id', '=', product_id)]
        if only_active:
            domain.append(('state', '=', 'active'))
        product_mapping = self.search(domain)
        if product_mapping.ids:
            return product_mapping
        return []


class YujuMappingModel(models.Model):
    _name = "yuju.mapping.model"

    name = fields.Char('Modelo Mapeo')
    code = fields.Char('Codigo')

class YujuMappingField(models.Model):
    _name = "yuju.mapping.field"

    name = fields.Char('Yuju Field')
    field = fields.Char('Odoo Field')
    default_value = fields.Char('Odoo Field Default Value')
    fieldtype = fields.Selection([('integer', 'Numerico'), ('char', 'Cadena'), ('relation', 'Relacional')], 'Odoo Field Type')
    model = fields.Many2one('yuju.mapping.model', 'Modelo Mapeo')

    @api.model
    def update_mapping_fields(self, record_data, modelo):
        fvalues = self.env['yuju.mapping.field.value']
        mapping_model = self.env['yuju.mapping.model'].search([('code', '=', modelo)], limit=1)
        if mapping_model:
            logger.debug("## Mapping model found")
            mapping_field_ids = self.search([('model', '=', mapping_model.id)])
            logger.debug("## Mapping field ids")
            for row in mapping_field_ids:
                yuju_field = row.name
                odoo_field = row.field
                logger.debug(yuju_field)
                if yuju_field in record_data:
                    yuju_value = record_data.pop(yuju_field)
                    mapping_value_id = fvalues.search([('field_id', '=', row.id), ('name', '=', yuju_value)], limit=1)
                    if mapping_value_id:
                        mapping_value = mapping_value_id.value
                    else:
                        mapping_value = row.default_value                        

                    if row.fieldtype in ['integer', 'relation']:
                        mapping_value = int(mapping_value)
                    
                    record_data.update({odoo_field : mapping_value})

        return record_data

class YujuMappingFieldValue(models.Model):
    _name = "yuju.mapping.field.value"

    name = fields.Char('Yuju Value')
    value = fields.Char('Odoo Value')
    field_id = fields.Many2one('yuju.mapping.field', 'Odoo Field')
