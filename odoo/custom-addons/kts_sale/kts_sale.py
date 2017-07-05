# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from openerp import SUPERUSER_ID
from openerp import api, fields, models, _
import openerp.addons.decimal_precision as dp
from openerp.exceptions import UserError
from openerp.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT

class KtsQuotationRejection(models.Model):
    _name = "kts.quotation.rejection"
    _description = "Kts Sales Order Quotation Rejection Reason"
    name = fields.Char(string='Rejection Reason')
    
    
class KtsSaleOrder(models.Model):
    _inherit = 'sale.order'
    cancel_state = fields.Char(string='Cancel State', copy=False, readonly=True)
    rejection_reason= fields.Many2one('kts.quotation.rejection', string='Rejection Reason', index=True)
    origin_id= fields.Many2one('sale.order', string='Reference Id', index=True)
    
    @api.multi
    def action_cancel(self):
        if not self.rejection_reason:
            raise UserError(_('Please give us rejection reason!')) 
        return super(KtsSaleOrder, self).action_cancel()
    
    
    