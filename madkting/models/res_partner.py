# -*- coding: utf-8 -*-
# File:           res_partner.py
# Author:         Israel Calderón
# Copyright:      (C) 2019 All rights reserved by Madkting
# Created:        2019-03-20
from odoo import models, fields, api
from odoo import exceptions
from ..responses import results
from ..log.logger import logger

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def init(self):
        # Índice para búsquedas frecuentes por cliente y fecha
        # self._cr.execute("DROP INDEX IF EXISTS idx_partner_vat_type_index;")
        self._cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_partner_vat_type_index
            ON res_partner (type, vat)
            WHERE type in ('contact', 'invoice');
        """)

    def _search_partner_by_vat(self, company_id, vat_id, partner_type='contact'):
        vat_variations = [vat_id]
        if vat_id.find("-") < 0:
            vat_variations.append(f"{vat_id[:len(vat_id) - 1]}-{vat_id[-1]}")
        query = """
            SELECT id FROM res_partner
            WHERE company_id = %s AND type = %s
            AND vat = ANY(%s) AND active = TRUE
            LIMIT 1
        """
        logger.debug(f"Searching partner by VAT {vat_id} with variations {vat_variations} for company {company_id}")
        self.env.cr.execute(query, (company_id, partner_type, vat_variations))
        partner_id = self.env.cr.fetchone()
        logger.info(f"Partner ID found by VAT {vat_id}: {partner_id}")
        if partner_id:
            partner = self.browse(partner_id)
            return partner
        return
    
    def _map_customer_address_data(self, customer_data, config):
        country_code = customer_data.pop('country_code', None)
        country_id = self._get_country_id(country_code)
        if country_id:
            customer_data['country_id'] = country_id

        if not hasattr(self, 'l10n_mx_edi_colony'):
            customer_data.pop('l10n_mx_edi_colony', None)
        
        state_id = False
        state_name = customer_data.pop('l10n_mx_edi_locality', None)
        state_id = self._get_state_data(state_name, country_id, config)
        logger.debug(state_id)
        # return
        if state_id:
            customer_data["state_id"] = state_id

            if hasattr(self, 'city_id'):
                logger.debug("Busca ciudad en el catalogo.")
                city_name = customer_data.get("city")
                if city_name:
                    city_name = city_name.strip()
                logger.debug(city_name)
                city_id = self._get_city_id(city_name, state_id, country_id)
                if city_id:
                    logger.debug(f"Ciudad encontrada en catalogo {city_name}.")
                    customer_data["city_id"] = city_id
                # deprecated
                # else:
                #     logger.debug(f"La ciudad no fue encontrada en el catalogo {city_name}.")
                #     if state_data.get("city_name") and config and config.search_city_by_mapping:
                #         city_name = state_data['city_name']
                #         logger.debug(f"Busca ciudad en mapeos {city_name}")
                #         city_id = self._get_city_id(city_name, state_id, country_id)
                #         if city_id:
                #             logger.debug("Ciudad encontrada por mapeo..")
                #             customer_data["city"] = city_name
                #             customer_data["city_id"] = city_id
        return customer_data

    @api.model
    def create_customer(self, customer_data):
        """
        :type customer_data: dict
        :param customer_data: dictionary with customer data
        {
            'name': str,
            'tz': str, #'America/Mexico_City',
            'vat': str, # tax_id
            'comment': str,
            'function': str,
            'street': str,
            'street2': str,
            'zip': str,
            'city': str,
            'country_code': str, # MX
            'email': str,
            'phone': str,
            # 'mobile': str,
            'company_id': int,
            'company_name': str
        }
        :return:
        """
        logger.debug("CREAR CUSTOMER")
        logger.debug(customer_data)

        # Se agrega lista de campos validas disponibles para crear el cliente V19
        create_fields = ["vat", "email", "phone", "company_id", "name", "street", "street2", "zip", "city", 
                         "company_name", "comment", "tz", "active", "country_id"]
        
        create_customer_data = dict()
        for field in create_fields:
            if field in customer_data and customer_data[field] is not None:
                create_customer_data[field] = customer_data[field]

        customer_data = create_customer_data

        company_id = None
        if customer_data.get('company_id'):
            company_id = customer_data.get('company_id')

        config = self.env['madkting.config'].get_config(company_id)

        # defaults = {
        #     'active': True,
        #     'customer_rank': 1,
        #     'employee': False,
        #     'is_company': False,
        #     'industry_id': False,
        #     'color': 0
        # }
        # customer_data.update(defaults)
        # partners = {
        #     'delivery': customer_data.pop('shipping_address', dict()),
        #     'invoice': customer_data.pop('billing_address', dict())
        # }
        

        # if hasattr(self, 'partner_gid'):
        #     defaults['partner_gid'] = 0

        partner_exist = False
        partner_found = None
        if config and config.validate_partner_exists and customer_data.get('vat'):
            vat_id = customer_data.get('vat')
            partner_found = self._search_partner_by_vat(company_id, vat_id, partner_type='contact')
            if partner_found and partner_found.id:
                partner_exist = True

        if partner_exist:
            new_customer = partner_found
        else:
            customer_data = self._map_customer_address_data(customer_data, config=config)
            customer_data = self.update_mapping_fields(customer_data)
            try: 
                logger.info("## CUSTOMER DATA ##")
                logger.info(customer_data)
                new_customer = self.with_context(no_vat_validation=True).create(customer_data)
            except exceptions.AccessError as err:
                return results.error_result(
                    code='access_error',
                    description=str(err)
                )
            except Exception as ex:
                logger.exception(ex)
                return results.error_result(
                    code='create_costumer_error',
                    description='Error trying to create new costumer: {}'.format(ex)
                )
        
        if not new_customer or not new_customer.id:
            return results.error_result(
                code='create_costumer_error',
                description='Error trying to create new costumer.'
            )
        # warnings = list()
        
        # remove_fields = ['image', 'image_medium', 'image_small', 'image_1920',
        #                  'image_1024', 'image_512', 'image_256', 'image_128']
        # logger.debug("## NEW CUSTOMER CREATED ##")
        # logger.debug(new_customer)
        # new_customer_data = new_customer.copy_data()[0]
        # logger.debug(new_customer_data)
        # new_customer_data['id'] = new_customer.id
        # for field in remove_fields:
        #     new_customer_data.pop(field, None)
        # logger.debug("RETURN NEW CUSTOMER DATA")
        # logger.debug(new_customer_data)
        # return_data = {"id": new_customer.id}
        return results.success_result({"id": new_customer.id})

    @api.model
    def update_mapping_fields(self, customer_data, model='res.partner'):
        logger.debug("MAIN UPDATE MAPPING")
        customer_data = self.env['yuju.mapping.field'].get_field_mappings(record_data=customer_data, model=model)
        return customer_data

    def _update_parent_company_name(self, config, parent_customer, partner_address):
        if config.partner_name_invoice_address and partner_address.type == "invoice":
            if parent_customer.name != partner_address.name:
                parent_customer.name = partner_address.name
                parent_customer.message_post(body="Partner name updated with invoice address")
        return

    @api.model
    def add_address(self, customer_id, type_, address):
        """
        :param customer_id:
        :type customer_id:int
        :param type_: delivery or invoice
        :type type_: str
        :param address:
        :type address: dict
        :return:
        """

        logger.debug(f"Add address {address}")

        company_id = None
        if address.get('company_id'):
            company_id = address.get('company_id')

        config = self.env['madkting.config'].get_config(company_id)
        parent_customer = self.browse(customer_id)

        address_exist = False
        address_found = None
        logger.debug("BUSCA ADDRESS")
        logger.debug(type_)
        
        if config and config.validate_partner_exists:
            if address.get('vat') and parent_customer.company_id:
                address_found = self._search_partner_by_vat(
                    company_id=parent_customer.company_id.id, 
                    vat_id=address.get('vat'), 
                    partner_type=type_)
                if address_found and address_found.id:
                    address_exist = True
            elif address.get("name") and address.get("street"):

                domain = [
                    ('name', '=', address.get('name')),
                    ('street', '=', address.get('street')),
                    ('type', '=', type_),
                    ('parent_id', '=', customer_id),
                ]
                logger.debug(f"Search address with domain {domain}")
                address_found = self.env['res.partner'].search(domain, limit=1)
                if address_found and address_found.id:
                    address_exist = True
        
        if address_exist:
            new_address = address_found
            logger.debug("## ADDRESS FOUND ADDED ##")
            logger.debug(new_address)
            data = {'id': new_address.id}
            self._update_parent_company_name(config, parent_customer, new_address)
            return results.success_result(data=data)
        else:
            logger.debug(f"CREATE ADDRESS {address}")
            defaults = {
                'active': True,
                'customer_rank': 1,
                'employee': False,
                'is_company': False,
                'industry_id': False,
                'color': 0,
                'type': type_,
                'parent_id': customer_id,
                'country_id': parent_customer.country_id.id,
            }

            if hasattr(self, 'partner_gid'):
                defaults['partner_gid'] = 0

            address.update(defaults)
            address = self._map_customer_address_data(address, config=config)
            address = self.update_mapping_fields(address)
            try:
                new_address = self.with_context(no_vat_validation=True).create(address)
            except exceptions.AccessError as err:
                logger.exception(ex)
                return results.error_result(
                    code='access_error',
                    description=str(err)
                )
            except Exception as ex:
                logger.exception(ex)
                return results.error_result(
                    code='create_costumer_error',
                    description='Error trying to create new costumer address: {}'.format(ex)
                )
            else:
                logger.debug("## NEW ADDRESS ADDED ##")
                logger.debug(new_address)
                data = {'id': new_address.id}
                self._update_parent_company_name(config, parent_customer, new_address)
                return results.success_result(data=data)

    def _get_city_id(self, city_name, state_id, country_id):
        """
        :param city_name:
        :type city_name: str
        :return: int | None
        """
        if not city_name:
            return
        city_name = city_name.strip()
        try:
            city = self.env['res.city'].search([
                ('name', '=', city_name), 
                ('state_id', '=', state_id), 
                ('country_id', '=', country_id)
                ], limit=1)
        except Exception as e:
            logger.exception(e)
        else:
            if not city:
                return
            else:
                return city.id

    def _get_state_data(self, state_name, country_id, config):
        """
        :param state_name:
        :type state_name: str
        :return: int | None
        """
        if not state_name:
            return
        state_name = state_name.strip()        
        state_domain = [
            ('name', '=', state_name), 
            ('country_id', '=', country_id)
            ]
        state_found = self.env['res.country.state'].search(state_domain, limit=1)
        logger.debug(f"Country states found with domain {state_domain}: {state_found}")
        if not state_found:
            logger.debug(f"No state found with name {state_name} in country {country_id}")
            return
        return state_found.id

    def _get_country_id(self, country_code):
        """
        :param country_code:
        :type country_code: str
        :return: int | None
        """
        logger.info("## BUSCA PAIS ##")
        logger.info(country_code)
        country = self.env['res.country'].search([('code', '=', country_code)])
        logger.info(country)
        if not country:
            return
        elif len(country) != 1:
            return
        else:
            return country.id
