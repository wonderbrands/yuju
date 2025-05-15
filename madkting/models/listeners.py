from odoo.addons.component.core import Component
from ..log.logger import logger
from ..log.logger import logs

class MadktingStockMoveListener(Component):
    _name = 'madkting.stock.move.listener'
    _inherit = 'base.event.listener'
    _apply_on = ['stock.move']

    def on_record_create(self, record, fields=None):
        """
        :param record:
        :param fields:
        :return:
        """
        self.__send_stock_webhook(record)

    def on_record_write(self, record, fields=None):
        """
        :param record:
        :param fields:
        :return:
        """
        self.__send_stock_webhook(record)

    def on_record_unlink(self, record):
        """
        :param record:
        :return:
        """
        self.__send_stock_webhook(record)

    def __send_stock_webhook(self, record):
        """
        :param record:
        :return:
        """

        if isinstance(record, bool):
            logger.debug("Bool object for record")
            return

        company_id = record.company_id.id if record and record.company_id else None
        if not company_id:
            logger.debug("No company id for record")
            return
        # config = self.env['madkting.config'].get_config(company_id)

        # if not config:
        #     logger.warning("No config set in webhook listener")
        #     return

        record_state = getattr(record, 'state', None)

        if record_state in ['assigned', 'done', 'cancel']:

            if not record.product_id.webhook_pending:
                logger.info("Update product webhook pending")
                record.product_id.webhook_pending = True

            # if config.webhook_product_mapped and not record.product_id.id_product_madkting:
            #     post_message = f"Only mapped product can webhook {record.name}"
            #     logger.warning(post_message)
            #     if config.webhook_detail_enabled:
            #         record.product_id.message_post(body=post_message)
            # else:
            #     try:
            #         wh_records = self.env["yuju.webhook.record"]
            #         wh_records.prepare_webhook(record.product_id, record.company_id.id)
            #     except Exception as ex:
            #         logger.exception(ex)
            #         logs(ex)
            #         post_message = f"Error on webhook listener {record.name}: {ex}"
            #         record.message_post(body=post_message)
            #         if config.webhook_detail_enabled:
            #             record.product_id.message_post(body=post_message)

        
# https://apps.yuju.io/api/sales/in/2301?id_shop=1085876
