# -*- coding: utf-8 -*-
# File:           sale_order.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-03-20

from odoo import models, fields, api
from odoo import exceptions
from datetime import datetime
from ..log.logger import logger
from ..responses import results


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    channel = fields.Char('Marketplace')
    channel_id = fields.Integer('Channel Id')
    channel_order_reference = fields.Char('Marketplace Reference')
    channel_order_id = fields.Char('Marketplace Id')
    order_progress = fields.Char('Order Progress')
    payment_status = fields.Char('Payment Status')


    @api.model
    def mdk_create(self, order_data, **kwargs):
        logger.debug("### MDK CREATE ###")
        logger.debug(order_data)

        """
        :param order_data:
        {
            'company_id': int,
            'date_order': str,
            'validity_date': str, # YYYY-mm-dd
            'confirmation_date': str, # YYYY-mm-dd HH:dd:ss
            'note': str,
            'partner_id': int,
            'invoice_status': str,
            'warehouse_id': int,
            'channel': str, # madkting
            'channel_id': int, # madkting
            'channel_order_reference': str, # madkting
            'channel_order_id': str, # madkting
            'order_progress': str, # madkting
            'payment_status': str, # madkting
            'lines': [
                {
                    # 'order_id': int,
                    'name': str,
                    'sequence': int, # 10
                    'invoice_status': str, # 'to invoice'
                    'price_unit': float,
                    'price_subtotal': float,
                    'price_tax': float,
                    'price_total': float,
                    'price_reduce': float,
                    'price_reduce_taxinc': float,
                    'price_reduce_taxexcl': float,
                    'discount': float,
                    'product_id': int,
                    'product_uom_qty': float,
                    'product_uom': int,
                    'qty_delivered_method': str, #'stock_move'
                    'qty_delivered': float,
                    'qty_delivered_manual': float,
                    'qty_to_invoice': float,
                    'qty_invoiced': float,
                    'untaxed_amount_invoiced': float,
                    'untaxed_amount_to_invoice': float,
                    'salesman_id': int,
                    'currency_id': int, # search for id  based on currency key "MXN"
                    'company_id': int, # mapped by user
                    'order_partner_id': int, # client id
                    'is_expense': bool, # False
                    'is_downpayment': bool, # False
                    'state': str, # 'sale'
                    'customer_lead': int, # 0
                    'tax_rate': bool,
                }
            ]
        }
        :type order_data: dict
        :param kwargs:
            :tax_rate: int
            :set_tax_rate_by_product: bool
        :return: new sale.order
        :rtype: sale.order
        """
        config_settings = self.env['res.config.settings']
        picking_policy = config_settings.default_picking_policy
        tax_rate = kwargs.get('tax_rate')
        set_tax_rate_by_product = kwargs.get('set_tax_rate_by_product')
        company_id = order_data.get('company_id')

        if not picking_policy:
            picking_policy = 'direct'

        order_data['require_signature'] = False
        order_data['require_payment'] = True
        """
        # TODO: if a client has prices list enabled may cause conflicts since
        # the orders from marketplaces may not match client prices list data
        """
        """
        # Verifica si se envia lista de precios personalizada, y si esta existe en el sistema
        # en caso de que no exista o no se envie, se define la lista de precios default.
        """
        if "pricelist_id" in order_data:
            pricelist_id = order_data["pricelist_id"]
            pricelist_ids = self.env["product.pricelist"].search([('id', '=', pricelist_id)], limit=1)
            if not pricelist_ids:
                order_data['pricelist_id'] = 1
        else:
            order_data['pricelist_id'] = 1

        order_data['picking_policy'] = picking_policy
        order_data['date_order'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        if not order_data.get('invoice_status'):
            order_data['invoice_status'] = 'to invoice'

        field_errors = self._validate_order_fields(order_data=order_data)
        if field_errors:
            return results.error_result(code='required_fields_validation',
                                        description=', '.join(field_errors))
        tax_cache = dict()
        if tax_rate:
            tax_cache[tax_rate] = self.env['account.tax'] \
                                      .search([('type_tax_use', '=', 'sale'),
                                               ('amount', '=', tax_rate),
                                               ('active', '=', True),
                                               ('company_id', '=', company_id)],
                                              limit=1)
        lines = order_data.pop('lines')

        config = self.env['madkting.config'].get_config()

        if not config or not config.update_tracking_ref:
            if "carrier_tracking_ref" in order_data:
                order_data.pop("carrier_tracking_ref") 

        try:
            new_sale = self.create(order_data)

            if new_sale and config and config.update_order_name:
                new_sale.write({"name" : order_data.get("channel_order_reference")})

        except exceptions.AccessError as err:
            logger.exception(err)
            return results.error_result(
                code='access_error',
                description=str(err)
            )
        except Exception as ex:
            logger.exception(ex)
            return results.error_result(
                code='sale_create_error',
                description='The sale order counldn\'t be created because of the following exception: {}'
                .format(ex)
            )
        else:
            order_line_model = self.env['sale.order.line']
            for line in lines:
                product_tax_rate = line.pop('tax_rate', False)
                line['order_id'] = new_sale.id

                logger.info("#Update UOM if different!")
                product_id = line["product_id"]
                product_ids = self.env["product.product"].search([('id', '=', product_id)], limit=1)
                if product_ids:
                    uom_id = product_ids[0].uom_id.id
                    logger.info(uom_id)
                    logger.info(line["product_uom"])                    
                    if uom_id != line["product_uom"]:
                        line["product_uom"] = uom_id
                        logger.info(line["product_uom"])                        
                try:
                    new_line = order_line_model.sudo().create(line)
                except exceptions.AccessError as err:
                    logger.exception(err)
                    # TODO: cancel sale before delete
                    cancel_sale = new_sale.action_cancel()
                    if cancel_sale:
                        new_sale.sudo().unlink()
                    return results.error_result(
                        code='sale_line_access_error',
                        description='An exception has occurred trying to '
                                    'create a sale line for product {}. '
                                    'The transaction has been rolledback. '
                                    'Exception: {}'.format(line.get('product_id'), err)
                    )
                except Exception as lex:
                    logger.exception(lex)
                    # TODO: cancel sale before delete
                    cancel_sale = new_sale.action_cancel()
                    if cancel_sale:
                        new_sale.sudo().unlink()
                    return results.error_result(
                        code='sale_create_error',
                        description='An exception has occurred trying to '
                                    'create a sale line for product {}. '
                                    'The transaction has been rolledback. '
                                    'Exception: {}'.format(line.get('product_id'), lex)
                    )
                else:
                    if not set_tax_rate_by_product and tax_cache.get(tax_rate):
                        new_line.tax_id = tax_cache[tax_rate]
                        continue
                    if set_tax_rate_by_product and product_tax_rate:
                        if not tax_cache.get(product_tax_rate):
                            tax_cache[product_tax_rate] = self.env['account.tax'] \
                                                              .search([('type_tax_use', '=', 'sale'),
                                                                       ('amount', '=', product_tax_rate),
                                                                       ('active', '=', True),
                                                                       ('company_id', '=', company_id)],
                                                                      limit=1)
                        new_line.tax_id = tax_cache.get(product_tax_rate)
        return results.success_result(data=new_sale.get_data())

    def get_data(self):
        """
        :return: dictionary with sale order data
        :rtype: dict
        """
        self.ensure_one()
        data = self.copy_data()[0]
        data['lines'] = list()
        extra_fields = ['id', 'name', 'amount_total', 'amount_tax',
                        'amount_undiscounted', 'amount_untaxed',
                        'invoice_ids', 'picking_ids']

        line_extra_fields = ['id', 'order_id', 'invoice_status', 'price_subtotal',
                             'price_tax', 'price_total', 'price_reduce',
                             'price_reduce_taxinc', 'price_reduce_taxexcl',
                             'qty_delivered_method', 'qty_delivered',
                             'qty_delivered_manual', 'qty_to_invoice',
                             'qty_invoiced', 'untaxed_amount_invoiced',
                             'untaxed_amount_to_invoice', 'salesman_id',
                             'currency_id', 'company_id', 'order_partner_id']

        one_to_many_ids = ['invoice_ids', 'picking_ids']
        many_to_one_ids = ['order_id', 'salesman_id', 'currency_id',
                           'company_id', 'order_partner_id']

        for field in extra_fields:
            data[field] = getattr(self, field, False)
            if field in one_to_many_ids:
                data[field] = [int(id_) if id_ else bool(id_) for id_ in data[field]]

        for line in self.order_line:
            line_data = line.copy_data()[0]
            for line_field in line_extra_fields:
                line_data[line_field] = getattr(line, line_field, False)
                if line_field in many_to_one_ids:
                    line_data[line_field] = int(line_data[line_field]) if line_data[line_field] \
                                            else bool(line_data[line_field])
            data['lines'].append(line_data)

        data['create_date'] = self.create_date.isoformat(' ')
        data.pop('order_line')
        return data

    @api.model
    def update_order(self, order_id, order_data):
        """
        Update order attributes (order lines not supported yet)
        :param order_id: order to update
        :type order_id: int
        :param order_data: attributes to update in sale order
        :type order_data: dict
        :return:
        :rtype: dict
        """
        order = self.search([('id', '=', order_id)])

        if not order:
            return results.error_result(code='sale_not_exists',
                                        description='order {} doesn\'t exists'.format(order_id))
        order.ensure_one()
        updatable_attributes = ['note', 'partner_shipping_id', 'partner_invoice_id',
                                'validity_date', 'confirmation_date']
        updates = {attribute: value for attribute, value in order_data.items() if attribute in updatable_attributes}

        if not updates:
            return results.error_result(code='not_valid_data',
                                        description='The attributes you\'re trying to update are invalid')

        try:
            order.write(updates)
        except Exception as ex:
            return results.error_result(code='sale_update_error',
                                        description=str(ex))
        else:
            return results.success_result()


    @api.model
    def deliver_order(self, order_id=None, order=None, **kwargs):
        """
        :param order_id: sale order id
        :type order_id: int
        :param order: sale.order record
        :type order: odoo.api.sale.order
        :keyword kwargs:
            default_sale_products_origin int
            default_sale_products_destiny int
            picking_type_id int
            state str # 'done', 'draft', 'cancel', 'ready'
        :return:
        """
        if not order and not order_id:
            return results.error_result(code='missing_order_id',
                                        description='You must provide at least order_id')

        elif not order and order_id:
            order = self.search([('id', '=', order_id)])

        if not order or not order.id:
            return results.error_result(code='sale_not_exists',
                                        description='order {} doesn\'t exists'.format(order_id))

        if not kwargs.get('state'):
            return results.error_result(code='missing_state_argument',
                                        description='delivery state is mandatory')

        order.ensure_one()

        # if the order already has a pending delivery
        if len(order.picking_ids) == 1:
            current_delivery = order.picking_ids.sudo()
            current_id = current_delivery.id
            current_name = current_delivery.name
            state = kwargs.get('state')
            if current_delivery.state == 'done' or \
               current_delivery.state == state:
                current_data = current_delivery.copy_data()[0]
                current_data['id'] = current_id
                current_data['name'] = current_name
                current_data['state'] = current_delivery.state
                return results.success_result(data=current_data)

            if state == 'done':
                for line in current_delivery.move_lines.sudo():
                    line.sudo().write({
                        'quantity_done': line.product_uom_qty,
                        'state': 'done'
                    })
                current_delivery.action_done()
            current_data = current_delivery.copy_data()[0]
            current_data['id'] = current_id
            current_data['name'] = current_name
            current_data['state'] = current_delivery.state
            return results.success_result(data=current_data)

        warehouse_id = order.warehouse_id.id

        # get origin of products from params or from default query
        def _get_sale_prods_origin():
            products_origin = kwargs.get('default_sale_products_origin')
            if not products_origin:
                location = self.env['stock.location'] \
                               .sudo() \
                               .search([('company_id', '=', order.company_id.id),
                                        ('active', '=', True),
                                        ('name', '=', 'Stock')
                                        ])
                if len(location) == 1:
                    products_origin = location.id
            return products_origin

        # get destiny of products from params or from default query
        def _get_sale_prods_destiny():
            products_destiny = kwargs.get('default_sale_products_destiny')
            if not products_destiny:
                location = self.env['stock.location'] \
                               .sudo() \
                               .search([('company_id', '=', None),
                                        ('active', '=', True),
                                        ('name', '=', 'Customers')
                                        ])
                if len(location) == 1:
                    products_destiny = location.id
            return products_destiny

        # get picking type id from params or from default query
        def _get_picking_type():
            picking_type_id = kwargs.get('picking_type_id')
            if not picking_type_id:
                picking_type = self.env['stock.picking.type'] \
                                   .sudo() \
                                   .search([('name', '=', 'Delivery Orders'),
                                            ('warehouse_id', '=', warehouse_id),
                                            ('active', '=', True)
                                            ])
                if len(picking_type) == 1:
                    picking_type_id = picking_type.id
            return picking_type_id

        stock_picking = {
            'sale_id': order.id,
            'origin': order.name,
            'note': 'Delivery for order from madkting',
            'move_type': order.picking_policy,
            'date': datetime.now().isoformat(' '),
            'location_id': _get_sale_prods_origin(),
            'location_dest_id': _get_sale_prods_destiny(),
            'picking_type_id': _get_picking_type(),
            'partner_id': order.partner_id.id,
            'owner_id': False,
            'printed': False,
            'is_locked': True,
            'immediate_transfer': False,
            'message_main_attachment_id': False,
            'move_lines': list(),
            'state': kwargs.get('state')
        }

        for order_line in order.order_line:
            stock_picking['move_lines'].append((0, 0, {
                    'state': kwargs.get('state'),
                    'name': order_line.name,
                    'sequence': 10,
                    'priority': '1',
                    'date': datetime.now().isoformat(' '),
                    'company_id': order_line.company_id.id,
                    'date_expected': datetime.now().isoformat(' '),
                    'product_id': order_line.product_id.id,
                    'product_uom_qty': order_line.product_uom_qty,
                    'product_uom': order_line.product_uom.id,
                    'product_packaging': False,
                    'location_id': _get_sale_prods_origin(),
                    'location_dest_id': _get_sale_prods_destiny(),
                    'partner_id': order.partner_id.id,
                    'note': 'Delivery for order from madkting',
                    'origin': order.name,
                    'procure_method': 'make_to_stock',
                    'propagate': True,
                    'picking_type_id': _get_picking_type(),
                    'inventory_id': False,
                    'restrict_partner_id': False,
                    'warehouse_id': order.warehouse_id.id,
                    'sale_line_id': order_line.id,
                    'quantity_done': order_line.product_uom_qty
                    # 'product_qty': 1,
                }
            ))
        try:
            new_deliver = self.env['stock.picking'].create(stock_picking)
        except exceptions.AccessError as err:
            return results.error_result(
                code='access_error',
                description=str(err)
            )
        except Exception as ex:
            logger.exception(ex)
            return results.error_result(
                code='delivery_create_error',
                description='Sale delivery cannot be created because of the '
                            'following exception: {}'.format(ex)
            )
        else:
            if not new_deliver.sale_id.id:
                new_deliver.sale_id = order_id
            if new_deliver.state == 'done':
                new_deliver.action_done()
            deliver_data = new_deliver.copy_data()
            deliver_data['id'] = new_deliver.id
            deliver_data['name'] = new_deliver.name
            deliver_data['state'] = new_deliver.state
            return results.success_result(data=deliver_data)

    @api.model
    def invoice_order(self, order_id):
        """
        :param order_id:
        :type order_id: int
        :return:
        """
        if not order_id:
            return results.error_result(code='order_id_required',
                                        description='order_id is required')
        order = self.search([('id', '=', order_id)])

        if not order:
            return results.error_result(code='sale_not_exists',
                                        description='order {} doesn\'t exists'.format(order_id))
        order.ensure_one()

        if order.invoice_ids:
            invoice = order.invoice_ids
            invoice.ensure_one()
            # if invoice is cancelled skip this and try to create it
            if invoice.state != 'cancel':
                if invoice.state not in ['paid', 'ready']:
                    invoice.action_invoice_open()
                invoice_data = invoice.copy_data()[0]
                invoice_data['id'] = invoice.id
                invoice_data['name'] = invoice.name
                return results.success_result(data=invoice_data)

        try:
            ids = order.sudo().action_invoice_create(grouped=True)
        except exceptions.AccessError as err:
            return results.error_result(
                code='access_error',
                description=str(err)
            )
        except Exception as ex:
            logger.exception(ex)
            return results.error_result(code='invoice_create_error',
                                        description='The sale order cannot be invoiced because of '
                                                    'the following exception: {}'.format(ex))
        else:
            invoice = self.env['account.invoice'].search([('id', '=', ids[0])])
            if not invoice:
                return results.error_result(code='retrieve_invoice_error',
                                            description='Cannot retrieve invoice for sale order')
            invoice.ensure_one()
            invoice.action_invoice_open()
            invoice_data = invoice.copy_data()[0]
            invoice_data['id'] = invoice.id
            invoice_data['name'] = invoice.name
            return results.success_result(data=invoice_data)

    @api.model
    def charge_invoice(self, invoice_id, payment_method_id=None, journal_id=None):
        """
        :param invoice_id:
        :type invoice_id: int
        :param payment_method_id:
        :type payment_method_id: int
        :param journal_id:
        :type journal_id: int
        :return: True on success or False if the invoice is already charged
        :rtype: bool
        """
        invoice = self.env['account.invoice'].search([('id', '=', invoice_id)])

        if not invoice:
            return results.error_result(code='invoice_not_exists',
                                        description='invoice doesn\'t exists')
        invoice.ensure_one()

        if invoice.state == 'paid':
            return results.error_result(code='already_paid',
                                        description='invoice already paid')

        payment_model = self.env['account.payment']

        if not payment_method_id:
            payment_method = self.env['account.payment.method'] \
                                 .search([('payment_type', '=', 'inbound'),
                                          '|', ('code', '=', 'manual'),
                                               ('code', '=', 'electronic')])
            if len(payment_method) >= 1:
                payment_method_id = payment_method.sorted(lambda method: method.id)[0].id
            else:
                return results.error_result(
                    code='not_payment_method',
                    description='payment_method_id must be specified or at '
                                'least you must have one method type inbound '
                                'with code manual or electronic'
                )

        if not journal_id:
            journal = self.env['account.journal'] \
                          .search([('company_id', '=', invoice.company_id.id),
                                   ('active', '=', True),
                                   ('type', '=', 'bank')])
            if len(journal) >= 1:
                journal_id = journal.sorted(lambda j: j.id)[0].id
            else:
                return results.error_result(
                    code='not_account_journal',
                    description='journal_id must be specified or at least you '
                                'must have one account_journal active in your '
                                'company of type bank'
                )
        try:
            payment = payment_model.create({'amount': invoice.amount_total,
                                            'pay_date': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                                            'payment_type': 'inbound',
                                            'payment_method_id': payment_method_id,
                                            'journal_id': journal_id,
                                            'partner_type': 'customer'})
        except exceptions.AccessError as err:
            return results.error_result(
                code='access_error',
                description=str(err)
            )
        except Exception as ex:
            logger.exception(ex)
            return results.error_result(
                code='invoice_payment_error',
                description='payment for invoice couldn\'t be saved because '
                            'of the following exception: {}'.format(ex))
        else:
            payment.invoice_ids = [invoice_id]

        try:
            payment.post()
        except exceptions.AccessError as err:
            return results.error_result(
                code='access_error',
                description=str(err)
            )
        except Exception as ex:
            logger.exception(ex)
            return results.error_result(
                code='payment_post_error',
                description='Payment {} couldn\'t be posted because of the '
                            'following error: {}'.format(payment.id, ex)
            )

        try:
            invoice.action_invoice_paid()
        except exceptions.AccessError as err:
            return results.error_result(
                code='access_error',
                description=str(err)
            )
        except Exception as ex:
            logger.exception(ex)
            return results.error_result(
                code='invoice_update_payed',
                description='Error updating invoice to payed: {}'.format(ex)
            )
        else:
            return results.success_result()

    @api.model
    def cancel_order(self, order_id):
        """
        :param order_id:
        :type order_id: int
        :return: results dictionary
        :rtype: dict
        """
        sale_order = self.search([('id', '=', order_id)])
        warnings = list()

        if not sale_order:
            return results.error_result(code='sale_not_exists')

        if sale_order.state == 'cancel':
            return results.error_result(code='sale_already_cancelled')

        # validate if the sale lines moves are not done
        if sale_order.has_lines_not_cancellable():
            return results.error_result(
                code='sale_stock_move_done',
                description='The sale has stock moves with status done'
            )

        try:
            r = sale_order.action_cancel()
        except exceptions.AccessError as err:
            return results.error_result(
                code='access_error',
                description=str(err)
            )
        except Exception as ex:
            return results.error_result(
                code='cancel_error',
                description=str(ex)
            )
        else:
            if not r:
                return results.error_result('cancel_error')

            if sale_order.invoice_ids:
                if sale_order.has_journal_not_cancellable():
                    warnings.append(
                        'invoice couldn\'t be cancelled because of journal policy'
                    )
                else:
                    try:
                        sale_order.invoice_ids.action_cancel()
                    except Exception as ex:
                        warnings.append(
                            'invoice couldn\'t be cancelled: {}'.format(ex)
                        )
            return results.success_result(data=None, warnings=warnings)

    def _validate_order_fields(self, order_data):
        """
        :param order_data:
        :type order_data: dict
        :return: list of errors
        :rtype: list
        """
        errors = list()
        order_fields = {
            'company_id': int,
            'date_order': str,
            'validity_date': str,
            'confirmation_date': str,
            'note': str,
            'partner_id': int,
            'require_signature': bool,
            'require_payment': bool,
            'pricelist_id': int,
            'invoice_status': str,
            'payment_term_id': int,
            # 'team_id': int,
            'warehouse_id': int,
            'picking_policy': str,
            'channel': str,  # madkting
            'channel_id': int,  # madkting
            'channel_order_reference': str,  # madkting
            'channel_order_id': str,  # madkting
            'lines': list
        }
        for field, type_ in order_fields.items():
            if field not in order_data:
                errors.append('missing required field {}'.format(field))
                continue
            if not isinstance(order_data[field], type_):
                errors.append('field {} must be instance of {}'.format(field, type_))
        if errors:
            return errors

    def has_lines_not_cancellable(self):
        """
        :return:
        :rtype: bool
        """
        self.ensure_one()
        for line in self.order_line:
            if any(move.state == 'done' for move in line.move_ids):
                return True
        return False

    def has_journal_not_cancellable(self):
        """
        :return:
        :type: bool
        """
        self.ensure_one()
        invoice = self.invoice_ids
        invoice.ensure_one()
        for move in invoice.move_id:
            if any(not journal.update_posted for journal in move.journal_id):
                return True
        return False
