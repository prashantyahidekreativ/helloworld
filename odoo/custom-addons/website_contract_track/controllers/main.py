# -*- coding: utf-8 -*-
from openerp import SUPERUSER_ID 
from openerp.addons.web import http
from openerp.http import request
from openerp.exceptions import UserError, AccessError, ValidationError
from openerp.tools.translate import _

class WebsiteDemo(http.Controller):

    @http.route('/Contract', type='http', auth='public', website=True)
    def display_contract_tracker_form(self):
        #cr, context, pool = request.cr, request.context, request.registry

        #hr_employee = pool.get('hr.employee')
        #hr_employee_ids = hr_employee.search(cr, SUPERUSER_ID, [], context=context)
        #hr_employee_data = hr_employee.browse(cr, SUPERUSER_ID, hr_employee_ids, context=context)

        #values = {
         #         'employees' : hr_employee_data 
          #        }

        return request.website.render("website.contract_tracker", {})
    
    @http.route('/customercontract', type='json', auth='public', website=True)
    def display_contract_form(self, **kw):
        cr, context, pool = request.cr, request.context, request.registry
        serial_no=kw['params']['serial_no']
        contract_no=kw['params']['contract_no']
        contract = pool.get('kts.contract.customer')
        stock_production_lot=pool.get('stock.production.lot')
        contract_id=''
        if serial_no:
           lot_id = stock_production_lot.search(cr, SUPERUSER_ID, [('name','ilike',serial_no)], context=context)
           contract_id = contract.search(cr, SUPERUSER_ID, [('lot_ids','in',lot_id)], context=context)
           contract_ids = contract.browse(cr, SUPERUSER_ID, contract_id, context=context)
        elif contract_no:
             contract_id = contract.search(cr, SUPERUSER_ID, [('name','ilike',contract_no)], context=context)
             contract_ids = contract.browse(cr, SUPERUSER_ID, contract_id, context=context)
        values=[] 
        if contract_id:
           for line in contract_ids:
                if line.state in ('draft','inprocess'):
                    values.append({
                                   'draft':'draft'
                                   })
                else:
                    values.append ({
                       'name':line.name,
                       'partner_name':line.partner_id.name,
                       'date_active':line.date_activation,
                       'val_date':line.val_duration,
                      })
        return {'values':values}
        #elif not contract_id:
        #        return False
    
    @http.route('/service', type='http', auth='public', website=True)
    def display_service_tracker_form(self):
        return request.website.render("website.service_tracker", {})
    
    @http.route('/customerservice', type='http', auth='public', website=True)
    def display_service_form(self, **kw):
        cr, context, pool = request.cr, request.context, request.registry
        service = pool.get('kts.service.management')
        service_id = service.search(cr, SUPERUSER_ID, [('name','ilike',kw['product_serial_no'])], context=context)
        service_ids = service.browse(cr, SUPERUSER_ID, service_id, context=context)
        
        if service_id:
           values = {
                  'service' : service_ids 
                  }

           return request.website.render("website.service_form", values)
        elif not service_id:
                return request.website.render("website.error_form",{})
    