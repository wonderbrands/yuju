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

    def _fix_vat_number(self, vat, country_id):

        logger.debug("OVERRIDE FIX VAT NUMBER")
        logger.debug(vat)
        logger.debug(country_id)

        config = self.env['madkting.config'].get_config()

        if config.validate_doctype_nit:
            logger.debug("No fix vat number")
            return vat
        
        else:
            logger.debug("Call super fix vat number")
            res = super(ResPartner, self)._fix_vat_number(vat, country_id)
            logger.debug(f"VAT {res}")
            return res

    @api.model
    def update_mapping_fields(self, customer_data):

        logger.debug("OVERRIDE UPDATE MAPPING FIELDS")
        logger.debug(customer_data)

        config = self.env['madkting.config'].get_config()
        
        # if customer_data.get('doc_type') and customer_data.get('vat') and config.validate_doctype_nit:
        #     logger.debug("Se valida VAT y DOC TYPE")
        #     is_customer_rut = False
        #     customer_vat = customer_data.get("vat")
        #     if customer_vat and len(customer_vat) == 10:
        #         if customer_vat[0] in ["8", "9"] and customer_vat.find("-") < 0:
        #             customer_vat = f"{customer_vat[:len(customer_vat) - 1]}-{customer_vat[-1]}"
        #             customer_data["vat"] = customer_vat
        #             customer_data["doc_type"] = "RUT"
        #             is_customer_rut = True
        #             logger.debug(f"ES RUT {customer_vat}")
            
        #     if not is_customer_rut and config.doctype_default:
        #         customer_data["doc_type"] = config.doctype_default
        #         logger.debug(f"Se asigna DOC TYPE por default {config.doctype_default}")
        
        customer_vat = customer_data.get("vat")
        if config.vat_separator and customer_vat and customer_vat.find("-") < 0:
            customer_vat = f"{customer_vat[:len(customer_vat) - 1]}-{customer_vat[-1]}"
            customer_data["vat"] = customer_vat
        
        # if config.vat_prefix and customer_vat:
        #     customer_data["vat"] = f"{config.vat_prefix}{customer_vat}"
        #     logger.debug(f"Agrega prefijo al VAT {customer_data['vat']}")

        customer_data = super(ResPartner, self).update_mapping_fields(customer_data)
        return customer_data