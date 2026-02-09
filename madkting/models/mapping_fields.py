# -*- coding: utf-8 -*-
# File:           res_partner.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-07-19

from odoo import models, api, fields
from ..log.logger import logger

class YujuMappingModel(models.Model):
    _name = "yuju.mapping.model"
    _description = 'Yuju Mapping Model'

    name = fields.Char('Modelo Mapeo')
    code = fields.Char('Codigo')

class YujuMappingField(models.Model):
    _name = "yuju.mapping.field"
    _description = 'Yuju Mapping Fields'

    name = fields.Char('Yuju Field')
    field = fields.Char('Odoo Field')
    default_value = fields.Char('Odoo Field Default Value')
    fieldtype = fields.Selection([('integer', 'Numerico'), ('char', 'Cadena'), ('relation', 'Relacional')], 'Odoo Field Type')
    model = fields.Many2one('yuju.mapping.model', 'Modelo Mapeo')
    model_relation = fields.Many2one('yuju.mapping.model', 'Modelo Relacion')
    field_values = fields.One2many('yuju.mapping.field.value', 'field_id', 'Valores campos')
    company_id = fields.Many2one('res.company', 'Company')
    remove_after_process = fields.Boolean("Quitar campo despues del mapeo", help="Quita el campo de los datos que se envian despues de que son procesados.", default=True)
    mapping_type = fields.Selection([
        ("fields", "Mapeo de campos"),
        ("defaults", "Valores por Default"),
    ], "Tipo de Mapeo")

    @api.model
    def get_field_mappings(self, record_data, model, channel_id=None, ff_type=None, company_id=None):
        logger.debug(f"## Se buscan mapeo de campos {model} ##")
        logger.debug(record_data)

        mapping_model = self.env['yuju.mapping.model'].search([('code', '=', model)], limit=1)
        
        if not mapping_model: 
            logger.debug(f"No se encontraron mapeos para el model {model}")
            return record_data

        if not company_id:
            company_id = self.env.user.company_id.id
        mapping_fields = self.search([('model', '=', mapping_model.id), '|', ('company_id', '=', company_id), ('company_id', '=', False)])

        logger.debug("Mappings encontrados")
        logger.debug(mapping_fields)

        processed_fields = []
        for mapping in mapping_fields:
            tipo_mapeo = mapping.mapping_type
            yuju_field = mapping.name
            odoo_field = mapping.field
            default_value = mapping.default_value 
            tipo_campo = mapping.fieldtype
            model_rel = mapping.model_relation
            remove_after = mapping.remove_after_process

            logger.debug(f"Yuju Field: {yuju_field}")
            logger.debug(f"Tipo Mapeo: {tipo_mapeo}")

            if tipo_mapeo == "defaults":
                if tipo_campo in ["integer"]:
                    record_data[yuju_field] = int(default_value)
                else:
                    record_data[yuju_field] = default_value

                logger.debug(record_data[yuju_field])

            elif tipo_mapeo == "fields":
                
                if yuju_field not in record_data:
                    continue

                yuju_value = record_data.get(yuju_field)
                logger.debug(f"Yuju Value: {yuju_value}")
                if yuju_field not in processed_fields and remove_after:
                    processed_fields.append(yuju_field)
                
                if not yuju_value:
                    logger.debug("Valor Yuju nulo")
                    if default_value:
                        mapping_value = default_value

                        if tipo_campo in ['integer', 'relation']:
                            mapping_value = int(mapping_value)
                        
                        update_data = {odoo_field : mapping_value}
                        logger.debug(f"Asigna valor por default {update_data}")
                        record_data.update(update_data)
                    continue

                if tipo_campo == "relation":
                    logger.debug("Tipo campo mapeo: RELATION")
                    try:
                        model_code = model_rel.code
                        rel_value = self.env[model_code].search(['|', ('name', '=ilike', yuju_value), ('code', '=ilike', yuju_value)], limit=1)
                    except Exception as e:
                        logger.error(f'No se pudo obtener informacion del modelo {model_code}, validar que el modelo exista y tenga acceso, {e}')
                    else:
                        logger.debug(f"Valor encontrado en el mapeo {yuju_value}, del modelo {model_code}: {rel_value}")
                        if rel_value:
                            mapping_value = rel_value.id
                            update_data = {odoo_field : mapping_value}
                            record_data.update(update_data)
                        else:
                            logger.debug(f"No se encontro valor relacionado a {yuju_value}")
                            if default_value:
                                logger.debug(f"Se asigna valor por default {update_data}")
                                mapping_value = int(default_value)
                                update_data = {odoo_field : mapping_value}
                                record_data.update(update_data)
                        continue
                else:
                    logger.debug(f"Tipo campo mapeo: {tipo_campo}")

                    if not mapping.field_values:
                        logger.debug("No hay reglas de mapeo se asigna valor Yuju.")
                        mapping_value = yuju_value
                        update_data = {odoo_field : mapping_value}
                        record_data.update(update_data)
                        continue
                    else:
                        logger.debug("Se consultan reglas de mapeo")
                        domain = [("field_id", "=", mapping.id), ('name', '=', yuju_value)]

                        if channel_id and ff_type:
                            domain.append(('channel_id', '=', channel_id))
                            domain.append(('ff_type', '=', ff_type))

                        logger.debug(f"Busca mapping por dominio {domain}")
                        mapping_value_id = mapping.field_values.search(domain, limit=1)

                        if not mapping_value_id:
                            domain = [("field_id", "=", mapping.id), ('name', '=', yuju_value)]

                            if channel_id and ff_type:
                                domain.append(('channel_id', '=', False))
                                domain.append(('ff_type', '=', False))
                        
                        logger.debug(f"Busca mapping por dominio {domain}")
                        mapping_value_id = mapping.field_values.search(domain, limit=1)

                        if mapping_value_id:
                            logger.debug("#Actualiza datos por campos mapeados")
                            mapping_value = mapping_value_id.value
                            logger.debug(mapping_value)

                        else:
                            logger.debug("No se encontraron reglas de mapeo")
                            if default_value:
                                logger.debug("Se asigna valor por default")
                                mapping_value = default_value
                            else:
                                logger.debug("No tiene valor por default, se asigna valor Yuju")
                                mapping_value = yuju_value

                        if tipo_campo in ['integer']:
                            mapping_value = int(mapping_value)

                        update_data = {odoo_field : mapping_value}
                        logger.debug(update_data)
                        record_data.update(update_data)
                        
                        continue

        if processed_fields:
            for pf in processed_fields:
                if pf in record_data:
                    record_data.pop(pf)

        return record_data

class YujuMappingFieldValue(models.Model):
    _name = "yuju.mapping.field.value"
    _description = 'Yuju Mapping Fields Values'

    name = fields.Char('Yuju Value')
    value = fields.Char('Odoo Value')
    channel_id = fields.Char('ID Canal')
    ff_type = fields.Selection([
        ('fbm', "Vendedor"),
        ('fbc', "Marketplace"),
        ('mix', "Mix"),
        ('flex', "Flex"),
    ], 'Tipo FF')
    field_id = fields.Many2one('yuju.mapping.field', 'Odoo Field')

# DEPRECATED
class YujuMappingCustom(models.Model):
    _name = "yuju.mapping.custom"
    _description = 'Yuju Mapping Custom Orders'

    name = fields.Char('Campo')
    value = fields.Char('Valor por defecto')
    value_type = fields.Selection([('number', 'Numero'), ('char', 'Cadena')], default='char', string='Tipo de Valor')
    custom_values = fields.One2many('yuju.mapping.custom.value', 'custom_id', 'Valores custom')
    modelo = fields.Selection(
        [('sales', 'Ventas'), ('invoices', 'Facturas')], 'Tipo de modelo')
    company_id = fields.Many2one('res.company', 'Company')
    
# DEPRECATED
class YujuMappingCustomValue(models.Model):
    _name = "yuju.mapping.custom.value"
    _description = 'Yuju Mapping Custom Values'

    name = fields.Char('Valor Custom')
    channel_id = fields.Char('Channel Id')
    ff_type = fields.Char('FF Type')
    custom_id = fields.Many2one('yuju.mapping.custom', 'Campo custom')


