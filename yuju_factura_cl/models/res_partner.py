# -*- coding: utf-8 -*-
# File:           madkting_config.py
# Author:         Gerardo Lopez
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2023-04-18

import requests
import stdnum

from odoo import models, fields, api
from odoo import exceptions
from datetime import datetime
from ..log.logger import logger
from ..responses import results

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # def format_vat_co(self, vat):
    #     logger.debug("FORMAT VAT CO")
    #     return vat

    def _fix_vat_number(self, vat, country_id):

        logger.debug("OVERRIDE FIX VAT NUMBER")
        logger.debug(vat)
        logger.debug(country_id)

        config = self.env['madkting.config'].get_config()

        if config and config.validate_doctype_nit:
            logger.debug("No fix vat number")
            return vat
        
        else:
            logger.debug("Call super fix vat number")
            res = super(ResPartner, self)._fix_vat_number(vat, country_id)
            logger.debug(f"VAT {res}")
            return res

        
        
        # code = self.env['res.country'].browse(country_id).code if country_id else False
        # vat_country, vat_number = self._split_vat(vat)
        # logger.debug(vat_country)
        # logger.debug(vat_number)
        # if code and code.lower() != vat_country:
        #     logger.debug(code)
        #     logger.debug("Return")
        #     return vat
        # stdnum_vat_fix_func = getattr(stdnum.util.get_cc_module(vat_country, 'vat'), 'compact', None)
        # logger.debug(stdnum_vat_fix_func)
        # #If any localization module need to define vat fix method for it's country then we give first priority to it.
        # format_func_name = 'format_vat_' + vat_country
        # logger.debug(format_func_name)

        # format_func = getattr(self, format_func_name, None) or stdnum_vat_fix_func
        # if format_func:
        #     logger.debug("Existe")
        #     logger.debug(format_func)
        #     vat_number = format_func(vat_number)
        #     logger.debug(vat_number)
        # return vat_country.upper() + vat_number

    @api.model
    def update_mapping_fields(self, customer_data):

        logger.debug("OVERRIDE UPDATE MAPPING FIELDS")
        logger.debug(customer_data)

        config = self.env['madkting.config'].get_config()
        
        if customer_data.get('doc_type') and customer_data.get('vat') and config and config.validate_doctype_nit:
            logger.debug("Se valida VAT y DOC TYPE")
            is_customer_rut = False
            customer_vat = customer_data.get("vat")
            if customer_vat and len(customer_vat) == 10:
                if customer_vat[0] in ["8", "9"] and customer_vat.find("-") < 0:
                    customer_vat = f"{customer_vat[:len(customer_vat) - 1]}-{customer_vat[-1]}"
                    customer_data["vat"] = customer_vat
                    customer_data["doc_type"] = "RUT"
                    is_customer_rut = True
                    logger.debug(f"ES RUT {customer_vat}")
            
            if not is_customer_rut and config.doctype_default:
                customer_data["doc_type"] = config.doctype_default
                logger.debug(f"Se asigna DOC TYPE por default {config.doctype_default}")

            if config and config.vat_prefix:
                customer_data["vat"] = f"{config.vat_prefix}{customer_data['vat']}"
                logger.debug(f"Agrega prefijo al VAT {customer_data['vat']}")


        customer_data = super(ResPartner, self).update_mapping_fields(customer_data)
        return customer_data