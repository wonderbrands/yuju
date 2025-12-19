from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    def _pre_action_done_hook(self):
        _logger.info("Override _pre_action_done_hook Yuju")
        vals = super(StockPicking, self)._pre_action_done_hook()
        _logger.info(vals)
        _logger.info(self.env.context)
        if isinstance(vals, dict):
            if (
                vals.get('type') == 'ir.actions.act_window' and
                vals.get('res_model') == 'stock.backorder.confirmation' and 
                self.env.context.get("from_yuju", False) # validate context yuju to create backorder
            ):
                _logger.info("Process backorder automatically from Yuju")
                pickings_to_validate = self.env.context.get(
                    'button_validate_picking_ids')
                if pickings_to_validate:
                    pickings_to_validate = self.env['stock.picking'].browse(
                            pickings_to_validate).with_context(skip_backorder=True)
                    if self.env.context.get('is_partial'):
                        return pickings_to_validate.button_validate()
                    else:
                        return pickings_to_validate\
                            .with_context(picking_ids_not_to_backorder=pickings_to_validate.ids)\
                            .button_validate()

        return vals