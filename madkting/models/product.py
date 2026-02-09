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
import json
import logging
import math

_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
    _inherit = "product.product"

    id_product_madkting = fields.Char('Id product madkting', size=50)
    tipo_producto_yuju = fields.Selection([('dropship', 'Dropship'), ('mto', 'MTO')],
                                            string='Tipo Ruta Producto', 
                                            help='En caso de no tener stock como se procesará Yuju el pedido para este producto, \n'
                                                 'Dropship: Lo surte el proveedor \n' 
                                                 'MTO: Se compra y lo surte la empresa')
    
    webhook_pending = fields.Boolean('Webhook pending', default=False)
    webhook_price_pending = fields.Boolean('Webhook price pending', default=False)
    webhook_data = fields.Text('Webhook data', default='')
    webhook_last_update = fields.Char('Fecha ultimo webhook', default='')

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
                                 'type' : str,
                                #  'detailed_type' : str,
                                 'id_product_madkting': (int, str)}

    def split_into_chunks(
        self, to_split, chunks_size: int
    ):
        """Split a list into chunks of the given size.

        Args:
            to_split: List to be splitted.
            chunks_size: Size of the chunks.

        Yields:
            Chunks of the given size.
        """
        for i in range(0, len(to_split), chunks_size):
            next_size = i + chunks_size
            yield to_split[i:next_size]

    def _get_product_stock(self, product, location_ids, company_id):
        locations = {}
        stock_product = 0

        for location_id in location_ids:
            try:
                qty_in_branch = product.with_context({"location" : location_id}).free_qty
                locations.update({
                    str(location_id) : qty_in_branch
                })
                stock_product += qty_in_branch
            except Exception as e:
                logger.exception("Error getting product stock")
                pass

        stock_data = {
            "product_id" : product.id,
            "company_id" : company_id,
            "default_code" : product.default_code,
            "stock" : stock_product,
            "quantities": locations
        }
        
        return stock_data, locations
    
    def _get_stock_products(self, products, location_ids, company_id):
        result_data = []
        product_ids = products.ids

        if not product_ids or not location_ids:
            return {}

        for product in products:
            product_stock = {
                "product_id" : product.id,
                "company_id" : company_id,
                "default_code" : product.default_code,
                "stock" : 0,
                "quantities": {}
            }

            for location_id in location_ids:
                try:
                    qty_in_branch = product.with_context({"location" : location_id}).free_qty
                    if product.default_code == "REFINED":
                        logger.info("REFINED")
                        logger.info(type(location_id))
                        logger.info(qty_in_branch)
                    product_stock['quantities'].update({
                        str(location_id) : qty_in_branch
                    })
                    product_stock['stock'] += qty_in_branch
                except Exception as e:
                    logger.exception(f"Error getting product stock {e}")

            result_data.append(product_stock)

        logger.debug("## RESULT DATA SIMPLE ##")
        logger.debug(result_data)

        return result_data

    def get_stock_products(self, products, location_ids, company_id):
        config = self.env['madkting.config'].get_config(company_id)
        if config.simple_stock_locations:
            return self._get_stock_products(products, location_ids, company_id)
        
        result_data = []
        product_ids = []
        product_ids = products.ids        
        
        if not product_ids or not location_ids:
            return {}
        
        for product in products:
            
            result_data.append({
                "product_id" : product.id,
                "company_id" : company_id,
                "default_code" : product.default_code,
                "stock" : 0,
                "quantities": {}
            })
        
        # Inicializar todo en 0
        stock_by_product = {
            product_id: {
                location_id: 0.0 for location_id in location_ids
            } for product_id in product_ids
        }

        stock_data = self.env['stock.quant'].read_group(
            domain=[
                ('product_id', 'in', product_ids),
                ('location_id', 'in', location_ids),
                ('company_id', '=', company_id)
            ],
            fields=['product_id', 'location_id', 'quantity:sum', 'reserved_quantity:sum'],
            groupby=['product_id', 'location_id'],
            lazy=False
        )

        # Sobrescribir los valores encontrados
        for line in stock_data:
            product = line['product_id'][0]
            location = line['location_id'][0]
            available = line['quantity'] - line['reserved_quantity']
            stock_by_product[product][location] = available

        logger.debug("## STOCK DATA ##")
        logger.debug(stock_by_product)

        for result in result_data:
            product_id = result['product_id']
            if product_id in stock_by_product:
                result['quantities'] = stock_by_product[product_id]
                result['stock'] = sum(stock_by_product[product_id].values())

        logger.debug("## RESULT DATA ##")
        logger.debug(result_data)

        return result_data
    
    def _get_location_ids(self, config, with_channels=True):
        """
        Get the location IDs from the configuration.
        :param config: Configuration record.
        :return: List of location IDs.
        """
        location_ids = []
        stock_locations = config.stock_source_multi
        if with_channels and config.stock_source_channels:
            stock_locations = f"{stock_locations},{config.stock_source_channels}"

        for location in stock_locations.split(','):
            location_id = int(location)
            if location_id not in location_ids:
                location_ids.append(location_id)

        # TODO: Se requiere agregar una funcionalidad para agrupar el stock por ubicaciones
        # en configuraciones con varios niveles de ubicaciones.
        # if config.stock_locations_children:
        #     locations = self.env["stock.location"].browse(location_ids)
        #     location_ids = self.env["stock.location"].search([('id', 'child_of', locations.ids)]).ids
        
        locations = self.env["stock.location"].browse(location_ids)
        return locations.ids

    # def process_webhooks(self):
    #     logger.info("## PREPARE WEBHOOKS ##")
    #     config_ids = self.env['madkting.config'].with_context(
    #             prefetch_fields=[
    #                 'company_id',
    #                 'stock_source_multi',
    #                 'webhook_stock_enabled',
    #                 'webhook_stock_cron_enabled',
    #                 'webhook_product_mapped',
    #                 'webhook_product_batchsize',
    #                 'webhook_auto_send_enabled'
    #             ]).search([])
        
    #     batchsize = 20
    #     product_data = []
    #     processed_webhooks = False
    #     for config in config_ids:

    #         if not config.stock_source_multi or not config.webhook_stock_enabled or not config.webhook_stock_cron_enabled:
    #             logger.debug("Webhook stock cron not enabled in config")
    #             continue

    #         domain = [('webhook_pending', '=', True)]
    #         if config.webhook_product_mapped:
    #             domain.append(('id_product_madkting', '!=', False))
            
    #         product_ids = self.with_context(
    #             prefetch_fields=[
    #                 'default_code', 
    #                 'id_product_madkting'
    #             ]).search(domain)

    #         if not product_ids:
    #             logger.info("No hay productos pendientes de webhook")
    #             return results.success_result([])

    #         processed_webhooks = True

    #         company_id = config.company_id.id
    #         if config.webhook_product_batchsize:
    #             batchsize = config.webhook_product_batchsize

    #         location_ids = self._get_location_ids(config)
    #         stock_data = self.get_stock_products(
    #             products=product_ids,
    #             location_ids=location_ids,
    #             company_id=company_id
    #         )

    #         wh_records = self.env["yuju.webhook.record"]
    #         for product_data in self.split_into_chunks(stock_data, batchsize):
    #             # product_data = self.process_webhook_chunk(product_ids=prod_ids, config=config, company_id=company_id, location_ids=location_ids)
    #             auto_send = config.webhook_auto_send_enabled
    #             wh_records.prepare_webhook_cron(webhook_body=product_data, company_id=company_id, type_webhook='stock', auto_send=auto_send)

    #     if processed_webhooks:
    #         product_ids.write({'webhook_pending': False, "webhook_last_update": fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')})    
        
    #     return results.success_result(product_data)
    
    def write(self, values):
        # Check if we need to update price for products
        need_update = False
        config_ids = self.env['madkting.config'].search([])
        for config in config_ids:
            if config.webhook_price_enabled:
                need_update = True
                break
        if need_update and "lst_price" in values:
            values["webhook_price_pending"] = True
        return super(ProductProduct, self).write(values)
    
    def _get_price(self):
        _logger.debug("## GET PRICE ##")
        _logger.debug(self._origin)
        _logger.debug(self._origin.id)
        product = self._origin
        new_price = self.lst_price
        config = self.env['madkting.config'].get_config()
        if config and config.default_pricelist:
            pricelist_id = int(config.default_pricelist)
            pricelist = self.env['product.pricelist'].browse(pricelist_id)
            res = pricelist._get_product_price(product, 1.0)
        else:
            res = new_price
        return res    
    
    def update_price_webhook(self, product_ids, company_id):
        """
        Updates the price of a product and sends a webhook if enabled in the configuration.
        :type product: product.product
        :type company_id: int
        :type new_price: float
        :return: None
        """
        logger.debug("## UPDATE PRICE WEBHOOK ##")
        logger.debug(f"Company: {company_id}")
        webhook_data = []
        for product in product_ids:
            logger.debug(product.id)
            new_price = product._get_price()
            price_data = {
                "product_id" : product.id,
                "company_id" : company_id,
                "default_code" : product.default_code,
                "price" : new_price,
            }
            webhook_data.append(price_data)

        if webhook_data:        
            wh_records = self.env["yuju.webhook.record"]
            wh_records.prepare_webhook_cron(webhook_body=webhook_data, company_id=company_id, type_webhook='price', auto_send=True)        
        return
    
    def process_price_webhooks(self):
        logger.info("## PREPARE PRICE WEBHOOKS ##")
        config_ids = self.env['madkting.config'].search([])
        product_ids = self.search([('webhook_price_pending', '=', True)])

        if not product_ids:
            logger.info("No hay productos pendientes de webhook")
            return results.success_result([])
        
        batchsize = 20
        product_data = []
        processed_webhooks = False
        for config in config_ids:
            
            if not config.webhook_price_enabled:
                continue

            if config.webhook_product_mapped:
                product_record_ids = [product for product in product_ids if product.id_product_madkting]
                if not product_record_ids:
                    logger.info("No hay productos pendientes de webhook con id_product_madkting")
                    continue
            else:
                product_record_ids = [product for product in product_ids]

            processed_webhooks = True

            for prod_ids in self.split_into_chunks(product_record_ids, batchsize):
                self.update_price_webhook(prod_ids, config.company_id.id)

        if processed_webhooks:
            product_ids.write({'webhook_price_pending': False})
        
        return results.success_result(product_data)
    
    def schedule_send_webhook(self):
        config_ids = self.env['madkting.config'].search([])
        for config in config_ids:
            if config.webhook_auto_send_enabled:
                logger.debug(f"Auto send enabled, skipping scheduled send {config.company_id.id}")
                continue
            
            # webhook_limit = 10
            # if config.webhook_product_limit:
            #     webhook_limit = config.webhook_product_limit
            #     logger.debug(f"Using webhook limit from config: {webhook_limit}")
            
            batchsize = 10
            if config.webhook_product_batchsize:
                batchsize = config.webhook_product_batchsize
                logger.debug(f"Using webhook batchsize from config: {batchsize}")
            
            logger.debug("## SCHEDULE SEND WEBHOOKS ##")
            wh_records = self.env["yuju.webhook.record"]
            wh_ids = wh_records.search([
                ('event', '=', 'stock_update'),
                ('product_id', '=', False),
                ('state', '=', 'draft'),
                ('company_id', '=', config.company_id.id)
            ], limit=1, order="date_webhook asc")
            
            if not wh_ids:
                logger.debug("No hay webhooks pendientes de envio, se buscan con product_id != False")            
                wh_ids = wh_records.search([
                    ('event', '=', 'stock_update'),
                    ('product_id', '!=', False),
                    ('state', '=', 'draft'),
                    ('company_id', '=', config.company_id.id)
                ], limit=batchsize, order="date_webhook asc")
            
            if wh_ids.ids:             
                logger.debug(f"## SEND WEBHOOKS: {wh_ids.ids} ##")
                grouped_webhook = []
                for wh in wh_ids:
                    if wh.product_id and wh.data:
                        wh_data = json.loads(wh.data)
                        if isinstance(wh_data, list) and len(wh_data) == 1:
                            grouped_webhook.append(wh_data[0])
                            wh.state = 'done'
                            wh.date_send_webhook = fields.Datetime.now()
                    else:
                        logger.debug("Sending webhook without product_id or data")
                        wh.send_webhook()

                if grouped_webhook:
                    logger.debug(f"Preparing webhook with {len(grouped_webhook)} items")
                    for chunk in self.split_into_chunks(grouped_webhook, batchsize):
                        wh_records.prepare_webhook_cron(
                            webhook_body=chunk, 
                            company_id=config.company_id.id, 
                            type_webhook='stock', 
                            auto_send=True, 
                            product_id=False)

        return True

    def show_qty(self):
        qty_available = self.with_context({'location' : 8}).qty_available
        free_qty = self.with_context({'location' : 8}).free_qty
        post_message = f"Qty {qty_available}."
        post_message2 = f"Free Qty {free_qty}."
        logger.debug(f"## QTY IN BRANCH: {post_message}")
        logger.debug(f"## QTY IN BRANCH: {post_message2}")

    def send_webhook_action(self, auto_send=True, config=None):
        """
        :param product_id:
        :type product_id: int
        :return:
        :rtype: dict
        """
        logger.debug(f"Env: {self.env.company}")
        logger.debug(f"Cr: {self.env.cr}")
        logger.debug(f"Dbname: {self.env.cr.dbname}")
        logger.debug(f"Autosend: {auto_send}")

        product_id = self.ids[0] if self.ids else None

        if not config:
            logger.debug("Config not found in params.")
            config = self.env['madkting.config'].get_config()
            if not config:
                logger.warning("No config set in webhook listener")
                return results.error_result('config_not_found', 'No configuration found for webhook')
        
        company_id = config.company_id.id if config.company_id else None

        if not company_id:
            logger.warning("No company id for record")
            return results.error_result('company_not_found', 'No company found for webhook')

        if not config.webhook_stock_enabled or not config.stock_source_multi:
            post_message = "stock webhook not enabled in config"
            self.message_post(body=post_message)

        if config.webhook_product_mapped and not self.id_product_madkting:
            self.message_post(body="Error al lanzar webhook: El producto no esta mapeado con Yuju")
            return
        
        location_ids = self._get_location_ids(config)

        locations = self.env["stock.location"].browse(location_ids)

        stock_data = {
            "product_id" : product_id,
            "company_id" : company_id,
            "default_code" : self.default_code,
            "stock" : 0,
            "quantities": {}
        }
        
        for location_id in locations.ids:
            try:
                qty_in_branch = self.with_context({"location" : location_id}).free_qty
                stock_data['quantities'].update({
                    str(location_id) : qty_in_branch
                })
                stock_data['stock'] += qty_in_branch
            except Exception as e:
                logger.exception(f"Error getting product stock: {e}")

        wh_records = self.env["yuju.webhook.record"]
        wh_records.prepare_webhook_cron(webhook_body=[stock_data], company_id=company_id, type_webhook='stock', auto_send=auto_send, product_id=product_id)

        return results.success_result()
    
    def send_price_webhook_action(self):
        """
        :param product_id:
        :type product_id: int
        :return:
        :rtype: dict
        """
        logger.debug(f"Env: {self.env.company}")
        logger.debug(f"Cr: {self.env.cr}")
        logger.debug(f"Dbname: {self.env.cr.dbname}")
        for product in self:
            # if not product.id_product_madkting:
            #     product.message_post(body="Error al lanzar webhook: El producto no esta mapeado con Yuju")
            #     return
            config_ids = self.env['madkting.config'].search([])
            for config in config_ids:
                if not config.webhook_price_enabled:
                    post_message = "price webhook not enabled in config"
                    product.message_post(body=post_message)
                    continue
                company_id = config.company_id.id

                try:
                    self.update_price_webhook([product], company_id)
                except Exception as ex:
                    logger.debug("###Exception Ocurred on Sending Price Webhook")
                    logger.debug(ex)
                    post_message = f"Error sending price webhook {product.name}: {ex}"
                    product.message_post(body=post_message)
        return results.success_result()

    @api.model
    def get_stock_data(self, location_id):
        config = self.env['madkting.config'].get_config()
        if config and config.webhook_product_mapped:
            product_ids = self.with_context(
                prefetch_fields=[
                    'id_product_madkting', 
                    'default_code',
                    'lst_price'
                ]).search([
                    ('id_product_madkting', '!=', False)])
        else:
            product_ids = self.with_context(
                prefetch_fields=[
                    'id_product_madkting', 
                    'default_code'
                ]).search([
                    ('is_storable', '=', True),
                    ('default_code', '!=', False)
                ])
        
        company_id = config.company_id.id if config and config.company_id else None
        location_ids = self._get_location_ids(config, with_channels=False)
        stock_data = self.get_stock_products(
            products=product_ids,
            location_ids=location_ids,
            company_id=company_id
        )
        product_data = []
        for el in stock_data:
            product_data.append({
                "product_id" : str(el['product_id']),
                "sku" : el['default_code'],
                # "price" : el['stock'],
                "stock" : el['stock']
            })
        logger.debug("## STOCK DATA ##")
        logger.debug(product_data)
        # response = {"data" : [product_data]}
        return results.success_result(product_data)
    
    # @api.model
    # def get_stock_product(self, product_ids, company_id=None):
    #     if not product_ids:
    #         return results.error_result("required_param", f"Product_ids param required {product_ids}")

    #     if company_id:
    #         config_ids = self.env['madkting.config'].search([("company_id", "=", int(company_id))])
    #     else:
    #         config_ids = self.env['madkting.config'].search([])

    #     if not config_ids:
    #         return results.error_result("not_found", f"Config not found {company_id}")        

    #     product_ids = self.env["product.product"].search([("id", "in", product_ids)])

    #     if not product_ids:
    #         return results.error_result("not_found", f"Product not found {product_ids}")
        
    #     product_company = {}
        
    #     for config in config_ids:

    #         company_id = config.company_id.id
    #         product_company[str(company_id)] = []

    #         location_ids = []
    #         stock_locations = config.stock_source_multi
    #         if config.stock_source_channels:
    #             stock_locations = f"{stock_locations},{config.stock_source_channels}"

    #         for location in stock_locations.split(','):
    #             location_id = int(location)
    #             if location_id not in location_ids:
    #                 location_ids.append(location_id)

    #         for product in product_ids:
    #             product_stock, locations = self._get_product_stock(product, location_ids, company_id)
    #             product_company[str(company_id)].append(product_stock)

    #     logger.debug("## STOCK DATA ##")
    #     logger.debug(product_company)
    #     return results.success_result(product_company)

    # @api.model
    # def send_webhook_by_id_product_madkting(self, id_product_madkting, company_id):
    #     """
    #     :param id_product_madkting:
    #     :type id_product_madkting: int
    #     :return:
    #     :rtype: dict
    #     """
    #     product_ids = self.search([('id_product_madkting', '=', id_product_madkting)])

    #     if not product_ids:
    #         return results.error_result('product_not_found',
    #                                     'product_id not found')

    #     for product in product_ids:
    #         try:
    #             yuju_records = self.env["yuju.webhook.record"]
    #             yuju_records.prepare_webhook(product, company_id)
    #         except Exception as ex:
    #             logger.debug("###Exception Ocurred on Sending Webhook")
    #             logger.debug(ex)        
            
    #     return results.success_result()

    @api.model
    def _create_supplier_product(self, supplier_data):  
        logger.debug("## CREATE SUPPLIER PRODUCT ##")      
        try:
            supplier_id = self.env['res.partner'].search(['|', ('email', '=', supplier_data.get('email')), ('vat', '=', supplier_data.get('rfc'))], limit=1)
            logger.debug(supplier_id)
            if not supplier_id.id:
                logger.debug("## Supplier not exists ##")
                supplier_id = self.env['res.partner'].create({
                    "name" : supplier_data.get('name'),
                    "phone" : supplier_data.get('contact'),
                    "email" : supplier_data.get('email'),
                    "vat" : supplier_data.get('rfc'),
                })
        except Exception as e:
            # No se pudo crear el proveedor
            logger.exception(e)
            pass
        else:
            logger.debug("## ELSE ##")
            try:
                logger.debug(self)
                logger.debug(self.seller_ids)
                if not self.seller_ids:
                    self.write({
                        "seller_ids" : [(0, 0, {
                            "name" : supplier_id.id,
                            "product_uom" : 1,
                            "price" : supplier_data.get('cost', 1)
                        })]
                    })
            except Exception as e:
                logger.exception(e)
                pass

    @api.model
    def update_mapping_fields(self, product_data):
        product_data = self.env['yuju.mapping.field'].get_field_mappings(product_data, 'product.product')
        return product_data

    @api.model
    def update_product(self, product_data, product_type, id_shop=None):
        """
        :param product_data:
        :type product_data: dict
        :param product_type: type of the product being updated: 'product' or 'variation'
        :type product_type: str
        :return:
        :rtype: dict
        """
        logger.debug("### UPDATE PRODUCT ###")
        logger.debug(product_data)
        logger.debug(id_shop)
        product_id = product_data.pop('id', None)
        if not product_id:
            return results.error_result('missing_product_id',
                                        'product_id is required')

        product = self.with_context(active_test=False) \
                      .search([('id', '=', product_id)])
        if not product:
            return results.error_result('product_not_found',
                                        'The product you are looking for does not exists in odoo or has been deleted')
        
        config = self.env['madkting.config'].get_config()

        supplier_data = False
        if product_data.get('provider'):
            supplier_data = product_data.pop('provider')
            product._create_supplier_product(supplier_data)

        if 'type' in product_data and product_data['type'] == 'product':
            product_data['type'] = 'consu'
            # product_data['is_storable'] = True

        if 'detailed_type' in product_data:
            product_data.pop('detailed_type')

        fields_validation = self.__validate_update_fields(fields=product_data,
                                                          product_type=product_type)
        if not fields_validation['success']:
            logger.debug(fields_validation)
            return fields_validation

        is_mapping = False
        if product_data.get('is_mapping'):
            product_data.pop('is_mapping')
            is_mapping = True
        
        is_multi_shop = False
        if product_data.get('is_multi_shop'):
            product_data.pop('is_multi_shop')
            is_multi_shop = True

        fields_validation['data'] = self.update_mapping_fields(fields_validation['data'])

        if 'image' in fields_validation['data']:
            fields_validation['data']['image_1920'] = fields_validation['data'].pop('image', None)

        fields_validation.pop('attributes', None)
        fields_validation['data'].pop('attributes', None)

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
        
        related_skus = []
        related_ids = []
        
        parent = product.product_tmpl_id
        for pv in parent.product_variant_ids:
            related_skus.append(pv.default_code)
            related_ids.append(pv.id_product_madkting)

        logger.debug("Related Skus")
        logger.debug(related_skus)

        logger.debug("Related Ids")
        logger.debug(related_ids)

        updatable_sku = fields_validation['data'].get('default_code')
        id_yuju = fields_validation['data'].get('id_product_madkting')

        is_related = False if updatable_sku not in related_skus and id_yuju not in related_ids else True

        logger.debug("Is Related")
        logger.debug(is_related)
        
        # Se quita el default code de la actualizacion, agreado en multi shop, este campo no es editable desde yuju 
        # ya que una vez asignado no puede modificarse
        if 'default_code' in fields_validation['data']:
            
            if product.default_code:
                fields_validation['data'].pop('default_code')

        # Si el producto cuenta actualmente con un id_product_madkting, el mapeo ya esta hecho y no debe sobre-escribirse
        # En caso de querer hacer el mapeo, debe eliminarse por script o manualmente el id_product_madkting del registro
        # Esto permitira que las nuevas tiendas mapeadas a este mismo producto no reemplacen la referencia original y 
        # se manejen por la tabla de mapeo al enviar el webhoook 
        if 'id_product_madkting' in fields_validation['data']:

            if product.id_product_madkting:
                fields_validation['data'].pop('id_product_madkting')

        # Si se realiza un mapeo a un catalogo que ya esta mapeado actualmente, el formulario tendra el campo company_id
        # con un valor establecido, lo cual para efectos del modulo multi shop, el catalogo de productos sera compartido
        # por lo que el campo company_id se establecera como False
        if is_multi_shop and config.product_shared_catalog_enabled:
            if "company_id" in fields_validation['data'] and fields_validation['data']['company_id']:
                fields_validation['data']['company_id'] = False
        
        logger.debug("#### DATA TO WRITE ####")
        logger.debug(fields_validation['data'])

        if "barcode" in fields_validation["data"]: 
            barcode = fields_validation["data"]["barcode"]
            if not barcode:
                # Drop empty barcode because constraint product_product_barcode_uniq
                fields_validation["data"].pop("barcode")
                logger.debug("Pop barcode..")
            else:
                logger.debug("## SEARCH BARCODE UPDATE ##")
                product_ids = self.with_context(active_test=False).search([('barcode', '=', barcode), ('id', '!=', product_id)])
                if product_ids.ids:
                    logger.warning(f'El codigo de barras ya esta previamente registrado {barcode}')

                    if config.validate_barcode_exists:               
                        return results.error_result(code='duplicated_barcode',
                                                description='El codigo de barras ya esta previamente registrado')
                    else:
                        fields_validation["data"].pop("barcode")

        logger.debug("## Fields validation data")
        logger.debug(fields_validation['data'])
        try:
            product.write(fields_validation['data'])
            # if config and config.update_parent_list_price and fields_validation['data'].get('list_price'):
            #     logger.debug("## UPDATE PARENT PRICE {}##".format(product.product_tmpl_id))
            #     product_list_price = fields_validation['data'].get('list_price')
            #     product.product_tmpl_id.write({"list_price" : product_list_price})

        except exceptions.AccessError as ae:
            logger.exception(ae)
            return results.error_result('access_error', ae)
        except Exception as ex:
            logger.exception(ex)
            logger.debug("AQUI")
            return results.error_result('save_product_update_exception', ex)
        else:
            return results.success_result()

    @api.model
    def create_variation(self, variation_data, id_shop=None):
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
        logger.debug("### CREATE VARIATION ###")
        logger.debug(variation_data)
        config = self.env['madkting.config'].get_config()
        parent_id = variation_data.pop('product_id', None)
        default_code = variation_data.get('default_code')
        id_product_madkting = variation_data.get('id_product_madkting')

        if not parent_id:
            return results.error_result('missing_product_id',
                                        'product_id is required')

        parent = self.search([('id', '=', parent_id)])
        if not parent:
            return results.error_result(
                'product_not_found',
                'Cannot find the parent product for this variation'
            )

        domain = [("default_code", "=", default_code), ("product_tmpl_id", "=", parent.product_tmpl_id.id)]
        logger.debug(domain)
        variation_exist = self.search(domain, limit=1)
        if variation_exist:
            logger.debug("## VARIATION EXISTS ###")
            logger.debug(variation_exist)
            logger.debug(variation_exist.product_tmpl_id)
            logger.debug(parent_id)
            logger.debug(id_product_madkting)
            if not variation_exist.id_product_madkting:
                variation_exist.write({"id_product_madkting": id_product_madkting})

            variation_data = variation_exist.get_data()
            logger.debug(variation_data)
            return results.success_result(variation_data)

        if variation_data.get('cost'):
            variation_data['standard_price'] = variation_data.pop('cost', None)

        if 'type' in variation_data and variation_data['type'] == 'product':
            variation_data['type'] = 'consu'
            variation_data['is_storable'] = True

        if 'detailed_type' in variation_data:
            variation_data.pop('detailed_type')

        fields_validation = self.__validate_update_fields(variation_data,
                                                          'variation')
        if not fields_validation['success']:
            return fields_validation

        logger.debug("## Fields validation")
        logger.debug(fields_validation)

        if "barcode" in variation_data: 
            barcode = variation_data.get("barcode")
            if not barcode:
                # Drop empty barcode because constraint product_product_barcode_uniq
                variation_data.pop("barcode")
                logger.debug("Pop barcode..")
            else:
                logger.debug("## SEARCH BARCODE UPDATE ##")
                product_ids = self.with_context(active_test=False).search([('barcode', '=', barcode)])
                if product_ids.ids:
                    logger.warning(f'El codigo de barras ya esta previamente registrado {barcode}')

                    if config.validate_barcode_exists:               
                        return results.error_result(code='duplicated_barcode',
                                                description='El codigo de barras ya esta previamente registrado')
                    else:
                        variation_data.pop("barcode")        

        attributes_structure = parent.attribute_lines_structure()
        variant_attributes = fields_validation['data'].pop('attributes')
        invalid_attributes = list()
        attribute_values = set()

        if 'image' in fields_validation['data']:
            fields_validation['data']['image_1920'] = fields_validation['data'].pop('image', None)

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
        v_data = fields_validation['data']
        logger.debug("## Current variation set")
        logger.debug(current_variations_set)

        logger.debug("## V Data")
        logger.debug(v_data)

        logger.debug("## Attribute values")
        logger.debug(attribute_values)

        logger.debug("## Variant Attribute")
        logger.debug(variant_attributes)

        if attribute_values in current_variations_set:
            for variation in parent.product_variant_ids:

                logger.debug("## Variant Data Attributes #1 ")
                logger.debug(variation.get_data().get('attributes'))

                if variant_attributes == variation.get_data().get('attributes'):
                    variation.write(fields_validation['data'])
                    return results.success_result(variation.get_data())

        new_attribute_lines = []
        for attribute, value in variant_attributes.items():
            # logger.in0fo(attributes_structure)
            value_id = attributes_structure[attribute].get('values').get(value)
            # logger.debug(value_id)
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

                new_attribute_lines.append({
                    'attribute_line_id': attributes_structure[attribute].get('attribute_line_id'),
                    'value_id': attribute_val.id
                })
                
        attribute_line_ids = [
                (1, a['attribute_line_id'], {'value_ids': [(4, a['value_id'])]}) for a in new_attribute_lines
        ]
        # logger.debug("## Attribute line ids")
        # logger.debug(attribute_line_ids)
        try:
            parent.product_tmpl_id.write({'attribute_line_ids': attribute_line_ids})
        except Exception as ex:
            logger.exception(ex)
            return results.error_result('variation_create_error', str(ex))

        new_variation_data = None
        v_data = fields_validation['data']

        # logger.debug("## New variation data 222")
        # logger.debug(new_variation_data)

        # logger.debug("## V data")
        # logger.debug(v_data)

        for variation in parent.product_variant_ids:
            logger.debug("## Variant Data Attributes #2 ")
            logger.debug(variation.get_data().get('attributes'))
            if variant_attributes == variation.get_data().get('attributes'):                      
                variation.write(fields_validation['data'])
                new_variation_data = variation.get_data()
                break

        if not new_variation_data:
            return results.error_result('new_variation_missing', 'The variation was created couldn\'t find it')

        return results.success_result(new_variation_data)

    @api.model
    def get_product(self, product_id, only_active=False, id_shop=None):
        """
        :param only_active:
        :type only_active: bool
        :param product_id:
        :type product_id: int
        :return:
        :rtype: dict
        """
        if not product_id:
            return results.error_result(
                'product_not_given',
                'The product id is null, it should be an integer'
            )

        product = self.with_context(active_test=only_active) \
                      .search([('id', '=', product_id)], limit=1)

        if not product:
            return results.error_result(
                'product_not_found',
                'The product that you are trying to get doesn\'t exists or has been deleted'
            )
        return results.success_result(product.get_data_with_variations())

    @api.model
    def get_variation(self, product_id, only_active=False, id_shop=None):
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
    def get_product_list(self, elements_per_page=50, page=1, id_shop=None):
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
    def product_count(self, id_shop=None):
        """
        :return:
        """
        return results.success_result(self.search_count([]))

    @api.model
    def deindex_products(self, product_ids, id_shop=None):
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
        data['standard_price'] = self.standard_price
        data['attributes'] = dict()
        for attribute_value in self.product_template_attribute_value_ids:
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
        data['id'] = self.id
        data['default_code'] = self.default_code
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

        config = self.env['madkting.config'].get_config()

        if product_type == 'product':
            updatable_fields = self.__update_product_fields

        else:
            updatable_fields = self.__update_variation_fields

            # if config and config.update_parent_list_price:
            #     updatable_fields.update({'list_price': (int, float)})

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
            for value in variation.product_template_attribute_value_ids:
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
