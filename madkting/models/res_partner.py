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
            'mobile': str,
            'company_id': int,
            'company_name': str
            'billing_address': {
                'name': str,
                'tz': str, #'America/Mexico_City',
                'vat': str, # tax_id
                'comment': str,
                'function': str,
                'street': str,
                'street2': str,
                'zip': str,
                'city': str,
                'country_code': str,
                'email': str,
                'phone': str,
                'mobile': str,
                'company_id': int,
                'company_name': str
            },
            'shipping_address': {
                'name': str,
                'tz': str, #'America/Mexico_City',
                'vat': str, # tax_id
                'comment': str,
                'function': str,
                'street': str,
                'street2': str,
                'zip': str,
                'city': str,
                'country_code': str,
                'email': str,
                'phone': str,
                'mobile': str,
                'company_id': int,
                'company_name': str
            }
        }
        :return:
        """
        logger.debug("CREAR CUSTOMER")
        logger.debug(customer_data)
        config = self.env['madkting.config'].get_config()

        defaults = {
            'active': True,
            'customer_rank': 1,
            'employee': False,
            'is_company': False,
            'industry_id': False,
            'color': 0
        }
        customer_data.update(defaults)
        partners = {
            'delivery': customer_data.pop('shipping_address', dict()),
            'invoice': customer_data.pop('billing_address', dict())
        }

        if hasattr(self, 'partner_gid'):
            defaults['partner_gid'] = 0

        country_code = customer_data.pop('country_code', None)
        country_id = self._get_country_id(country_code)
        if country_id:
            customer_data['country_id'] = country_id

        if not hasattr(self, 'l10n_mx_edi_colony'):
            customer_data.pop('l10n_mx_edi_colony', None)
        
        state_id = False
        state_name = customer_data.pop('l10n_mx_edi_locality', None)
        state_data = self._get_state_data(state_name, country_id)
        logger.debug(state_data)
        # return
        if state_data and state_data.get("id"):
            state_id = state_data['id']
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
                else:
                    logger.debug(f"La ciudad no fue encontrada en el catalogo {city_name}.")
                    if state_data.get("city_name") and config.search_city_by_mapping:
                        city_name = state_data['city_name']
                        logger.debug(f"Busca ciudad en mapeos {city_name}")
                        city_id = self._get_city_id(city_name, state_id, country_id)
                        if city_id:
                            logger.debug("Ciudad encontrada por mapeo..")
                            customer_data["city"] = city_name
                            customer_data["city_id"] = city_id

        customer_data = self.update_mapping_fields(customer_data)

        logger.debug(customer_data)

        partner_exist = False
        partner_found = None
        if config and config.validate_partner_exists and customer_data.get('vat'):
            vat_id = customer_data.get('vat')
            domain = [('vat', '=ilike', vat_id), ("type", "=", "contact")]
            logger.debug(domain)
            partner_found = self.search(domain, limit=1, order="id")
            if partner_found.id:
                partner_exist = True
            else:
                if vat_id.find("-") < 0:
                    vat_upd = f"{vat_id[:len(vat_id) - 1]}-{vat_id[-1]}"
                    domain = [('vat', '=ilike', vat_upd), ("type", "=", "contact")]
                    logger.debug(domain)
                    partner_found = self.search(domain, limit=1, order="id")
                    if partner_found.id:
                        partner_exist = True
        
        if partner_exist:
            new_customer = partner_found
        else:
            try: 
                logger.debug("## CUSTOMER DATA ##")
                logger.debug(customer_data)
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
        warnings = list()
        for type_, partner in partners.items():
            if not partner:
                continue
            r = self.add_address(customer_id=new_customer.id,
                                 type_=type_,
                                 address=partner)

            if not r['success']:
                warnings.extend(r['errors'])
        remove_fields = ['image', 'image_medium', 'image_small', 'image_1920',
                         'image_1024', 'image_512', 'image_256', 'image_128']
        new_customer_data = new_customer.copy_data()[0]
        new_customer_data['id'] = new_customer.id
        for field in remove_fields:
            new_customer_data.pop(field, None)
        return results.success_result(data=new_customer_data, warnings=warnings)

    @api.model
    def update_mapping_fields(self, customer_data, model='res.partner'):
        logger.debug("MAIN UPDATE MAPPING")
        customer_data = self.env['yuju.mapping.field'].get_field_mappings(record_data=customer_data, model=model)
        return customer_data

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

        config = self.env['madkting.config'].get_config()
        parent_customer = self.browse(customer_id)
        country_code = address.pop('country_code', None)
        country_id = self._get_country_id(country_code)

        if not country_id:
            country_id = parent_customer.country_id.id

        if not hasattr(self, 'l10n_mx_edi_colony'):
            address.pop('l10n_mx_edi_colony', None)
        
        state_id = False
        state_name = address.pop('l10n_mx_edi_locality', None)
        state_data = self._get_state_data(state_name, country_id)
        if state_data and state_data.get("id"):
            state_id = state_data['id']
            address["state_id"] = state_id
            if hasattr(self, 'city_id'):
                city_name = address.get("city")
                if city_name:
                    city_name = city_name.strip()
                city_id = self._get_city_id(city_name, state_id, country_id)
                if city_id:
                    address["city_id"] = city_id
                else:
                    logger.debug(f"La ciudad no fue encontrada en el catalogo {city_name}.")
                    if state_data.get("city_name") and config.search_city_by_mapping:
                        city_name = state_data['city_name']
                        logger.debug(f"Busca ciudad en mapeos {city_name}")
                        city_id = self._get_city_id(city_name, state_id, country_id)
                        if city_id:
                            logger.debug("Ciudad encontrada por mapeo..")
                            address["city"] = city_name
                            address["city_id"] = city_id
        
        defaults = {
            'active': True,
            'customer_rank': 1,
            'employee': False,
            'is_company': False,
            'industry_id': False,
            'color': 0,
            'type': type_,
            'parent_id': customer_id,
            'country_id': country_id
        }

        if hasattr(self, 'partner_gid'):
            defaults['partner_gid'] = 0

        address.update(defaults)

        address = self.update_mapping_fields(address)

        address_exist = False
        address_found = None
        logger.debug("BUSCA ADDRESS")
        logger.debug(type_)
        
        if config and config.validate_partner_exists:
            if type_ == "invoice" and address.get('vat'):
                vat_id = address.get('vat')
                domain = [('vat', '=ilike', vat_id), ("type", "=", type_)]
                logger.debug(domain)
                address_found = self.search(domain, limit=1, order="id")
                if address_found.id:
                    address_exist = True
                else:
                    if vat_id.find("-") < 0:
                        vat_upd = f"{vat_id[:len(vat_id) - 1]}-{vat_id[-1]}"
                        domain = [('vat', '=ilike', vat_upd), ("type", "=", type_)]
                        logger.debug(domain)
                        address_found = self.search(domain, limit=1, order="id")
                        if address_found.id:
                            address_exist = True
        
        if address_exist:
            new_address = address_found
            logger.debug("## ADDRESS FOUND ADDED ##")
            logger.debug(new_address)
            data = {'id': new_address.id}
            return results.success_result(data=data)
        else:
            logger.debug(f"CREATE ADDRESS {address}")
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
            city = self.env['res.city'].search([('name', 'ilike', city_name), ('state_id', '=', state_id), ('country_id', '=', country_id)])
        except Exception as e:
            logger.exception(e)
        else:
            if not city:
                return
            elif len(city) != 1:
                return
            else:
                return city.id

    def _get_state_data(self, state_name, country_id):
        """
        :param state_name:
        :type state_name: str
        :return: int | None
        """
        if not state_name:
            return
        config = self.env['madkting.config'].get_config()
        state_name = state_name.strip()
        city_name = None
        if config.search_state_by_mapping:
            logger.debug(f"Busca mapeo de estado {state_name}")
            domain = [('country_id', '=', country_id), ('name', 'ilike', state_name)]
            logger.debug(domain)
            res_mapping = self.env['yuju.mapping.state'].search(domain)
            logger.debug(res_mapping)
            if res_mapping:
                logger.debug("Mapeo de estado encontrado")
                if len(res_mapping) > 1:
                    logger.debug("Multiples resultados")
                    for res in res_mapping:
                        res_name = res.name_state.lower()
                        if res_name == state_name.lower():
                            logger.debug(f"Es igual: {res_name}")
                            state_name = res.name_state
                            city_name = res.name_city
                            logger.debug(state_name)
                            logger.debug(city_name)
                            break
                        else:
                            logger.debug(f"Es diferente: {res_name}")
                else:
                    state_name = res_mapping.name_state
                    city_name = res_mapping.name_city
                    logger.debug(state_name)
                    logger.debug(city_name)
        
        state_domain = [('name', 'ilike', state_name), ('country_id', '=', country_id)]
        state_results = self.env['res.country.state'].search(state_domain)
        logger.debug(f"Country states found with domain {state_domain}: {state_results}")
        if not state_results:
            return
        elif len(state_results) != 1:
            logger.debug("Multiples resultados, se busca coincidencia.")
            state_found = False 
            for res in state_results:
                res_lower = res.name.lower()
                if res_lower == state_name.lower():
                    logger.debug(f"Es igual: {res_lower}")
                    state_found = res
                    break
                else:
                    logger.debug(f"Es diferente: {res_lower}")
            if state_found:
                return {"id": state_found.id, "city_name": city_name}    
            return
        else:
            return {"id": state_results.id, "city_name": city_name}

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
