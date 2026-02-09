# -*- coding: utf-8 -*-
# File:           res_partner.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-07-19

from odoo import models, api, fields
from odoo import exceptions

import logging
_logger = logging.getLogger(__name__)

# class Pricelist(models.Model):
#     _inherit = "product.pricelist"

#     def write(self, vals):
#         _logger.info("Updating pricelist with vals: %s", vals)
#         return super(Pricelist, self).write(vals)
    
class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("Creating pricelist items with vals_list: %s", vals_list)
        res = super(PricelistItem, self).create(vals_list)
        _logger.info("Created pricelist items: %s", res)
        if res:
            # Check if we need to update price for products
            need_update = False
            config_ids = self.env['madkting.config'].search([])
            for config in config_ids:
                if config.webhook_price_enabled:
                    need_update = True
                    break
            if not need_update:
                # _logger.debug("No need to update price for products.")
                return res

            for item in res:
                if item.product_id:
                    item.product_id.webhook_price_pending = True
                elif item.product_tmpl_id:
                    products = self.env['product.product'].search([('product_tmpl_id', '=', item.product_tmpl_id.id)])
                    for p in products:
                        p.webhook_price_pending = True
        return res

    def write(self, vals):
        _logger.info("Updating pricelist item with vals: %s", vals)
        res = super(PricelistItem, self).write(vals)
        # Check if we need to update price for products
        need_update = False
        config_ids = self.env['madkting.config'].search([])
        for config in config_ids:
            if config.webhook_price_enabled:
                need_update = True
                break
        if not need_update:
            # _logger.debug("No need to update price for products.")
            return res

        for item in self:
            if item.product_id:
                item.product_id.webhook_price_pending = True
            elif item.product_tmpl_id:
                products = self.env['product.product'].search([('product_tmpl_id', '=', item.product_tmpl_id.id)])
                for p in products:
                    p.webhook_price_pending = True
        return res
    

