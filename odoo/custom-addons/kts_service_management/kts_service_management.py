from datetime import datetime, timedelta
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from openerp import models, fields, api, _
from openerp.exceptions import UserError
from openerp.addons.ktssarg_reports.ktssarg_reports import do_print_setup
import random
class kts_disciplinary_details(models.Model):
    _name='kts.disciplinary.details'
    log_date=fields.Date(string='Date', copy=False,)
    disciplinary_comment = fields.Char('Disciplinary Comment')
    action_by=logged_by = fields.Many2one('res.users', string='Action by' , default=lambda self:self.env.user.id,)
    employee_id=fields.Many2one('hr.employee', string='Employee Details', required=True, change_default=True, index=True, track_visibility='always')
    product_id=fields.Many2one('product.product', domain=[('type', '=', 'service')], string='Product', required=True, change_default=True, index=True, track_visibility='always')
    product_unit=fields.Many2one('product.uom', string='Unit', required=True, change_default=True, index=True, track_visibility='always')
    product_price=fields.Float('Price')
    service_management_id=fields.Many2one('kts.service.management', string='Material Details', required=True, change_default=True, index=True, track_visibility='always')
    invoice_flag=fields.Boolean(string='Invoice',default=False)
    
    @api.onchange('product_id')
    def onchange_Product(self):
        if self.product_id:
           domain = {'product_unit': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
           self.product_unit=self.product_id.uom_id
           self.product_price=self.product_id.list_price
           self.update({'product_unit':self.product_id.uom_id,
                        'product_price':self.product_id.list_price,
                        })
           return{'domain':domain}
        
class hr_employee(models.Model):
    _name = "hr.employee"
    _inherit = "hr.employee"
    disciplinary_line=fields.One2many('kts.disciplinary.details', 'employee_id', string='', nolable="1")
    technician = fields.Boolean('Technician')
    offroll = fields.Boolean('Offroll Technician')
    pan_no=fields.Char('PAN No.')
    pf_no=fields.Char('PF No.')
    esic_no=fields.Char('ESIC No.')
    uan_no=fields.Char('UAN No.')
    bank_name=fields.Char('Bank Name')

class kts_visit_details(models.Model):
    _name='kts.visit.details'
    name=fields.Char('Name')
    service_management_id=fields.Many2one('kts.service.management', string='Service Management', required=True, index=True,ondelete='cascade')
    emp_id = fields.Many2one('hr.employee', string='Employee Name', index=True)
    start_time=fields.Datetime(string='Start Date', copy=False,)
    end_time=fields.Datetime(string='End Date',  copy=False,)
    note = fields.Char('Note')
    attachment=fields.Binary("Image", attachment=True, help="This field holds the attachment.")
    product_id=fields.Many2one('product.product', domain=[('type', '=', 'service')], string='Product', required=True, change_default=True, index=True, track_visibility='always')
    product_unit=fields.Many2one('product.uom', string='Unit', required=True,)
    product_price=fields.Float('Price')
    visible_emp = fields.Selection(related='service_management_id.service',)
    invoice_flag=fields.Boolean(string='Invoice',default=False )
    state=fields.Selection([('draft','Draft'),('assigned','Assigned'),('in_progress','In Progress'),('done','Done'),('cancel','Cancel')],string='State',default='draft')
    
    @api.onchange('visible_emp')
    def onchange_visible_emp(self):
        if self.service_management_id.service:
            self.visible_emp = self.service_management_id.service     
            return {'domain':{'default_visible_emp':self.visible_emp}}
    
    @api.onchange('product_id')
    def onchange_Product(self):
        if self.product_id:
           domain = {'product_unit': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
           self.product_unit=self.product_id.uom_id
           self.product_price=self.product_id.list_price
           self.update({'product_price':self.product_id.list_price,
                        'product_unit':self.product_id.uom_id,
                        })
           return {'domain':domain}       
    @api.multi
    def _prepare_invoice_line(self):
        self.ensure_one()
        res = {}
        account = self.product_id.property_account_income_id or self.product_id.categ_id.property_account_income_categ_id
        if not account:
            raise UserError(_('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') % \
                            (self.product_id.name, self.product_id.id, self.product_id.categ_id.name))
        
        res = {  
            'account_id': self.service_management_id.partner_id.property_account_receivable_id.id,
            'price_unit': self.product_price,
            'name':self.product_id.name,
            'uom_id': self.product_unit.id,
            'product_id': self.product_id.id or False,
            
        }
        return res
    
    @api.multi
    def invoice_line_create(self, invoice_id):
        if self.product_id:
           for line in self:
               vals = line._prepare_invoice_line()
               vals.update({'invoice_id': invoice_id, 'visit_line': [(6, 0, [line.id])]})
               self.env['account.invoice.line'].create(vals)
    
    @api.multi
    def action_assign(self):
        self.write({'state':'assigned'})    
    
    @api.multi
    def action_process(self):
        self.write({'state':'in_progress'})    
    
    @api.multi
    def action_done(self):
        self.write({'state':'done'})    
    
    @api.multi
    def action_cancel(self):
        self.write({'state':'cancel'})    
    
   
class kts_nature_of_complaints(models.Model):
    _name='kts.service.management.type'
    name = fields.Char('Name')

class kts_sla(models.Model):
    _name='kts.sla'
    problem_priority = fields.Selection([('0','Low'), ('1','Normal'), ('2','High'),('3','higher'),('4','highest'),('5','Very Urgent')], 'Problem Priority')
    no_of_days=fields.Integer(string='No. of Days',)

class kts_contract_customer_inv(models.Model):
    _inherit='kts.contract.customer'
    service_ids=fields.One2many('kts.service.management','invcontract_id','service List') 
    end_customer_name=fields.Char('End Customer Name')
    end_customer_mob=fields.Char('End Customer Moblie No')
    
    @api.multi
    def _get_due_date(self,obj,num):
        self.ensure_one()
        if obj.no_proac_visit:
           freq=obj.contract_id.fre_pro_visit
           date=obj.date_activation
           if freq=='yearly':
              date1=fields.Datetime.from_string(date)
              date2=date1+relativedelta(months=12*num) 
              return fields.Datetime.to_string(date2)
           elif freq=='semiyearly':
              date1=fields.Datetime.from_string(date)
              date2=date1+relativedelta(months=6*num) 
              return fields.Datetime.to_string(date2)
           elif freq=='quat':
              date1=fields.Datetime.from_string(date)
              date2=date1+relativedelta(months=3*num) 
              return fields.Datetime.to_string(date2)
           elif freq=='monthly':
              date1=fields.Datetime.from_string(date)
              date2=date1+relativedelta(months=1*num) 
              return fields.Datetime.to_string(date2)
        else:
            return False  
        
    @api.multi
    def _get_due_date1(self):
        self.ensure_one()
        if self.no_ins_visit:
            no_days = self.due_days
            date1=fields.Datetime.from_string(self.date_activation)
            date2=date1+relativedelta(days=no_days) 
            return fields.Datetime.to_string(date2)
        else:
            return False   
    def _prepare_contract_line(self,order_id,contract_id,lot_obj):
     
        res = []  
        res.append({
                 'origin': order_id.id,
                 'partner_id': order_id.partner_id.id,
                 'type':contract_id.type,
                 'contract_id':contract_id.id,
                 'product_id': lot_obj.product_id.id or False,     
                 'val_duration': contract_id.val_duration,
                 'no_proac_visit':contract_id.no_proac_visit,
                 'no_ins_visit': contract_id.no_ins_visit, 
                 'no_free_visit':contract_id.no_free_visit,
                 'fre_pro_visit':contract_id.fre_pro_visit,
                 'date_creation':fields.Datetime.now(),
                 'date_activation':fields.Datetime.now(),
                 'team_id': order_id.team_id.id,   
                 'state':'inprocess',
                 'lot_ids':lot_obj.id,
                 'val_duration_date':fields.Datetime.to_string(fields.Datetime.from_string(fields.Datetime.now())+relativedelta(months=contract_id.val_duration))
              })
        return res

    @api.multi
    def contract_service_create(self,picking_obj):
        lines=[]
        for line in picking_obj.pack_operation_product_ids:
            if line.product_id.tracking == 'serial' and line.product_id.type != 'service':
                for line1 in line.pack_lot_ids:
                    if line1.qty>0:
#                         for move_line in picking_obj.move_lines:
#                             lot_ids=move_line.lot_ids.ids
#                             if lot_ids in line1.lot_id.id:
#                                 move=move_line
                        move=picking_obj.move_lines.filtered(lambda r: line1.lot_id in r.lot_ids )
                        if move.contract_id:
                            vals=self._prepare_contract_line(picking_obj.sale_id,move.contract_id,line1.lot_id)
                            contract_id=self.create(vals[0])
    
    @api.onchange('contract_id')
    def onchange_contract_id(self):
        vals={}
        if self.contract_id:
            vals.update({
            'val_duration':self.contract_id.val_duration,
            'no_proac_visit':self.contract_id.no_proac_visit,
            'no_ins_visit':self.contract_id.no_ins_visit,
            'due_days':self.contract_id.due_days,
            'no_free_visit':self.contract_id.no_free_visit,
            'fre_pro_visit':self.contract_id.fre_pro_visit,
            'type':self.contract_id.type,
                    })
            self.update(vals)
            return{'value':vals}
    
    @api.onchange('date_activation')
    def onchange_val_duration_date(self):
        if self.date_creation and self.date_activation:
            if self.date_activation < self.date_creation:
                self.update({'date_activation':False})
                return { 'value':{'date_activation':False},'warning':{'title':'UserError','message':'Date of activation should be greater than date of creation'}}
                
    @api.multi
    def action_activate(self):
        self.ensure_one()
        ret=super(kts_contract_customer_inv, self).action_activate()
        res={}
        res1={}
        
        service_obj = self.env['kts.service.management']
        if self.no_ins_visit:        
           res.update({
                 'partner_id': self.partner_id.id,
                 'address':self.partner_id.street or '',
                 'mobile':self.partner_id.mobile or '',
                 'email':self.partner_id.email or '',
                 'type':'sys_gen',
                 'service_type':'installation',
                 'logged_by':  self.origin.user_id and self.origin.user_id.id,   
                 'state':'plan',
                 'priority':'0',
                 'invcontract_id':self.id,   
                 'due_date': self._get_due_date1(),
                 'origin':self.origin.name, 
                 'date_logged':fields.Datetime.now()
                 })
           service_obj.create(res)
        if self.no_proac_visit:
            for i in range(1,self.no_proac_visit+1):
                res1.update({
                 'name': self.origin,
                 'partner_id': self.partner_id.id,
                 'address':self.partner_id.street or '',
                 'mobile':self.partner_id.mobile or '',
                 'email':self.partner_id.email or '',
                 'type':'sys_gen',
                 'service_type':'maintainance',
                 'logged_by':  self.origin.user_id and self.origin.user_id.id,   
                 'state':'plan',
                 'priority':'0',
                 'invcontract_id':self.id,   
                 'due_date': self._get_due_date(self,i),
                 'origin':self.origin.name, 
                 'date_logged':fields.Datetime.now()
                })
                service_obj.create(res1) 
        return ret     
    
    def amc_print(self,cr, uid, ids, context={}):
        this = self.browse(cr, uid, ids[0], context=context)
        report_name= 'amc_contract'
        name='AMC Contract'               
        context.update({'this':this, 'uiModelAndReportModelSame':False})
        return do_print_setup(self,cr, uid, ids, {'name':name, 'model':'kts.contract.customer','report_name':report_name},
                False,this.partner_id.id, context)
    
    def get_val_recs(self):
        so_line = self.origin.order_line
        for line in so_line:
             if line.product_id == self.product_id: price_unit=line.price_unit 
             else: price_unit=False
        return price_unit
    
    
    
     
class kts_service_management(models.Model):
    _name='kts.service.management'
    _order = 'id desc'
    name = fields.Char('Subject')
    service_id = fields.Integer('Id')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, index=True, track_visibility='always', domain=[('parent_id','=',False)])
    address = fields.Text('Address')
    mobile = fields.Char('Mobile No')
    email = fields.Char('Email')
    type = fields.Selection([('sys_gen','System generated'),('report_customer','Reported By customer')],'Type')
    service_type = fields.Selection([('installation','Installation Visit'),('maintainance','Maintainance Visit')],string='Service Type')
    priority = fields.Selection([('0','Low'), ('1','Normal'), ('2','High'),('3','higher'),('4','highest'),('5','Very Urgent')], 'Priority',default='0')  
    logged_by = fields.Many2one('res.users', string='Logged by')
    problem_logged=fields.Boolean(string='Problem Logged', )
    due_date=fields.Date(string='Due Date',  readonly=True,copy=False,)
    date_logged = fields.Datetime(string='Logged Date',  readonly=True, index=True,  copy=False)
    assigned_to = fields.Many2one('res.users', string='Resposible')
    date_assigned = fields.Datetime(string='Assigned Date',  readonly=True, index=True,  copy=False)
    date_accepted = fields.Datetime(string='Accepted Date',  readonly=True, index=True,  copy=False)
    date_inprocess = fields.Datetime(string='Inprocess Date',  readonly=True, index=True,  copy=False)
    date_done = fields.Datetime(string='Done Date',  readonly=True, index=True,  copy=False)
    date_cancel = fields.Datetime(string='Cancel Date',  readonly=True, index=True,  copy=False)
    nature_of_complaint = fields.Many2one('kts.service.management.type','Nature of complaint')
    state = fields.Selection([
        ('draft', 'Problem By'),
        ('plan', 'Plan'),
        ('new', 'Problem Logged'),
        ('assigned', 'Assigned'),
        ('accepted', 'Accepted'),
        ('in_process', 'In process'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ('reopened', 'Re-opened'),
        ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')    
    visit_line=fields.One2many('kts.visit.details', 'service_management_id', string='Visit lines',copy=True)
    invcontract_id=fields.Many2one('kts.contract.customer',string='AMC/Warranty')
    service = fields.Selection([('third_party','Third Party'),],'Service To Third Party')
    vendor_id = fields.Many2one('res.partner', string='Vendor',domain=[('supplier','=',True)])
    inv_call = fields.Boolean('inv flag for one time fn call',default=False)    
    closure_code = fields.Integer('Closure code')
    internal_closure_code = fields.Integer('Internal Closure Code') 
    picking_lines=fields.One2many('stock.picking','service_id',string='Picking Lines')
    service_inv_flag=fields.Boolean('Service Inv Flag',default=False)
    material_inv_flag=fields.Boolean('Material Inv Flag',default=False)
    invoice_lines=fields.One2many('account.invoice','service_id',string='Invoice Lines',readonly=True)
    end_customer_name=fields.Char('End Customer Name')
    end_customer_mob=fields.Char('End Customer Moblie No')
    
    _defaults = {
             'service_id': lambda self, cr, uid, context: self.pool.get('ir.sequence').next_by_code(cr, uid, 'kts.service.management.id') or _(0)
            }         
    
    @api.onchange('partner_id')
    def onchange_partner(self):
        if self.partner_id:
            contract_ids=self.env['kts.contract.customer'].search([('partner_id','=',self.partner_id.id),('state','=','act')])
            return {'domain':{'invcontract_id':[('id','in',contract_ids.ids)]}}
    @api.model
    def create(self,vals):
        if self._context:
            if vals.get('type') == 'sys_gen':
                vals.update({
                             'name':self.env['ir.sequence'].next_by_code('kts.service.management') or 'New',
                             })
                 
            else:
                vals.update({
                             'name':self.env['ir.sequence'].next_by_code('kts.service.management1') or 'New',
                             'type':'report_customer',
                             'service_type':'maintainance',
                             })
                
        return super(kts_service_management, self).create(vals)               
    
   
    @api.multi
    def kts_prepare_invoice(self):
        self.ensure_one()
        journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
        if not journal_id:
            raise UserError(_('Please define an accounting sale journal for this company.'))
        invoice_vals = {
            'name': self.partner_id.id or '',
            'type': 'out_invoice',
            'reference': self.name,
            'account_id': self.partner_id.property_account_receivable_id.id,
            'partner_id': self.partner_id.id,
            'currency_id': self.visit_line[0].product_id.currency_id.id,
            'fiscal_position_id': self.partner_id.property_account_position_id.id,
            'user_id': self.logged_by.id,
            'service_id':self.id,
        }
        return invoice_vals
    
    @api.multi
    def kts_create_invoice(self):
        if self.visit_line:
              inv_obj=self.env['account.invoice']         
              inv_data = self.kts_prepare_invoice()
              invoice = inv_obj.create(inv_data)
              res=[]
              for line in self.visit_line:
                  if line.invoice_flag:
                        account = line.product_id.property_account_income_id or line.product_id.categ_id.property_account_income_categ_id
                        if not account:
                            raise UserError(_('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') % \
                                            (line.product_id.name, line.product_id.id, line.product_id.categ_id.name))
                        
                        res.append( {  
                            'account_id': account.id,
                            'price_unit': line.product_price,
                            'name':line.product_id.name,
                            'uom_id': line.product_id.uom_id.id,
                            'product_id': line.product_id.id,
                            'invoice_id':invoice.id,
                            'quantity':1.0
                        })
                  for inv_line in res:
                         self.env['account.invoice.line'].create(inv_line)             
        else:
            raise UserError(_('Please select visit lines or Product lines to create invoice')) 
        self.write({'service_inv_flag': True})
        
    @api.multi
    def kts_payment_invoice(self):
        self.ensure_one()
        move_lines=[]
        for pick_line in self.picking_lines:
            for move_line in pick_line.move_lines:
                if move_line.invoice_flag and move_line.state=='done':
                    move_lines.append(move_line)
            
        if move_lines:
            inv_obj=self.env['account.invoice']         
            journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
            if not journal_id:
                raise UserError(_('Please define an accounting sale journal for this company.'))
            
            invoice_vals = {
                'name': self.partner_id.id or '',
                'type': 'out_invoice',
                'reference': self.name,
                'account_id': self.partner_id.property_account_receivable_id.id,
                'partner_id': self.partner_id.id,
                'currency_id': self.partner_id.currency_id.id,
                'fiscal_position_id': self.partner_id.property_account_position_id.id,
                'user_id': self.logged_by.id,
                'service_id':self.id,
            }
            
            invoice = inv_obj.create(invoice_vals)
            
            res = []
            for line in move_lines:
                account = line.product_id.property_account_income_id or line.product_id.categ_id.property_account_income_categ_id
                if not account:
                    raise UserError(_('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') % \
                                    (line.product_id.name, line.product_id.id, line.product_id.categ_id.name))
                
                res.append( {  
                    'account_id': account.id,
                    'price_unit': line.product_id.list_price,
                    'name':line.product_id.name,
                    'uom_id': line.product_uom.id,
                    'product_id': line.product_id.id,
                    'invoice_id':invoice.id,
                    'quantity':line.product_uom_qty
                })
            for inv_line in res:
                 self.env['account.invoice.line'].create(inv_line)
            self.write({'material_inv_flag': True})        

#         journal_domain = [
#                 ('type', '=', 'purchase'),
#                 ('company_id', '=', self.env.user.company_id.id),
#                 ('currency_id', '=', self.visit_line[0].product_id.currency_id.id),
#             ]
#         journal_id = self.env['account.invoice'].search(journal_domain, limit=1)
#         if not journal_id:
#             raise UserError(_('Please define an accounting sale journal for this company.'))
#         if self.service:
#             if self.pdc_asc:
#                partner_id=self.pdc_asc
#             else:
#                 raise UserError(_('Please assign pdc/asc'))   
#         invoice_vals = {
#             'name': partner_id.id or '',
#             'type': 'in_invoice',
#             'account_id': partner_id.property_account_payable_id.id,
#             'partner_id': partner_id.id,
#             'currency_id': self.visit_line[0].product_id.currency_id.id,
#             'fiscal_position_id': partner_id.property_account_position_id.id,
#             'user_id': self.logged_by.id,
#         }
#         return invoice_vals
#    
#     @api.multi
#     def kts_payment_invoice(self):  
#         if self.visit_line:
#             if self.service:
#                if self.pdc_asc:
#                   partner_id=self.pdc_asc
#                else:
#                   raise UserError(_('Please assign pdc/asc'))   
#                for line in self.visit_line: 
#                       inv_obj=self.env['account.invoice']         
#                       inv_data = self.kts_prepare_payment_inv(partner_id)
#                       invoice = inv_obj.create(inv_data)
#                       visit_type=self.service_type
#             
#                       if self.service: 
#                          type=self.service 
#                       
#                       incen_objs=self.env['kts.incentive.details'].search([('type','=',type),('visit_type','=',visit_type)])
#                       for obj in incen_objs:
#                           if obj.product_id:
#                              res = {}
#                              account = obj.product_id.property_account_expense_id or obj.product_id.categ_id.property_account_expense_categ_id
#                           if not account:
#                              raise UserError(_('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') % \
#                                   (obj.product_id.name, obj.product_id.id, obj.product_id.categ_id.name))
#         
#                           res = {  
#                                 'invoice_id':invoice.id,
#                                 'account_id': partner_id.property_account_receivable_id.id,
#                                 'price_unit': obj.product_id.list_price,
#                                 'name':obj.product_id.name,
#                                 'uom_id': obj.product_id.uom_id.id,
#                                 'product_id': obj.product_id.id,
#                                }
#                           self.env['account.invoice.line'].create(res)
#         else:
#             raise UserError(_('Select pdc/asc to make payment'))    
#             
    @api.multi
    @api.onchange('priority')
    def onchange_priority(self):
        self.ensure_one()  
        if self.priority and self.type == 'report_customer':
            rec = self.env['kts.sla'].search([('problem_priority','=',self.priority)])
            endDate=fields.Datetime.to_string(fields.Datetime.from_string(fields.Datetime.now()) + relativedelta(days=rec.no_of_days))
            self.update({'due_date':endDate})
            return {'domain':{'default_due_date':endDate}}
        else:
            return 

    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        """
        Update the following fields when the partner is changed:
        - Pricelist
        - Payment term
        - Invoice address
        - Delivery address
        """
        if not self.partner_id:
            self.update({
                'address': False,
                'mobile': False,
                'email': False,
            })
            return

        addr = self.partner_id.address_get(['delivery', 'invoice'])
        values = {
            'address': self.partner_id.street or False,
            'mobile': self.partner_id.mobile  or False,
            'email': self.partner_id.email  or False,
        }

       # if self.partner_id.user_id.id:
        #    values['user_id'] = self.partner_id.user_id.id
        #if self.partner_id.team_id.id:
        #    values['team_id'] = self.partner_id.team_id.id
        self.update(values)
   
    @api.multi
    def action_assign_problem(self):
        '''
        This function opens a window to compose an email, with the edi sale template message loaded by default
        '''
        if not self.assigned_to:
            raise UserError(_('Please assign this issue to superwiser !'))
        r = random.randint(1000,9999)
        self.write({'state': 'assigned','date_assigned':datetime.today(),'internal_closure_code':r})
        
        return True 
    
    @api.multi
    def action_log_problem(self):
        self.write({'state': 'new',
                    'problem_logged':True,
                    'date_logged':fields.Datetime.now()
                    })
        return True 

    @api.multi
    def action_accept_problem(self):
        '''
        This function opens a window to compose an email, with the edi sale template message loaded by default
        '''
        self.ensure_one()
        self.write({'state': 'accepted','date_accepted':datetime.today()})
        return {}
    
    @api.multi
    def action_inprogress_problem(self):
        '''
        This function opens a window to compose an email, with the edi sale template message loaded by default
        '''
        self.ensure_one()
        self.write({'state': 'in_process','date_inprocess':datetime.today()})
        return {}
    
    @api.multi
    def action_done_problem(self):
        '''
        This function opens a window to compose an email, with the edi sale template message loaded by default
        '''
        self.ensure_one()
        if self.visit_line:
            for line in self.visit_line:
                if line.state not in ('done','cancel'):
                    raise UserError(_('Visit lines are not in done/cancel state'))
        
        if self.picking_lines:
            for line in self.picking_lines:
                if line.state not in ('done','cancel'):
                    raise UserError(_('Picking lines are not in done/cancel state'))
        
        if not self.closure_code:
            raise UserError(_('Please Insert Clousure code to done it'))
        
        if self.closure_code != self.internal_closure_code:
            raise UserError(_('Please Insert Valid Clousure code it does not match'))
        
        self.write({'state': 'done','date_done':datetime.today()})
        
        return True
    
    @api.multi
    def action_reopen_problem(self):
        '''
        This function opens a window to compose an email, with the edi sale template message loaded by default
        '''
        self.ensure_one()
        self.write({'state': 'new'})
        return {}
    
    @api.multi
    def action_cancel_problem(self):
        '''
        This function opens a window to compose an email, with the edi sale template message loaded by default
        '''
        self.ensure_one()
        self.write({'state': 'cancel'})
        return {}
    
    @api.model
    def logged_service(self):
        service_log_obj=self.env['kts.service.log.conf'].search([])
        if not service_log_obj:
            raise UserError(_('Please Configure service log conf No of Days'))
        days=service_log_obj[0].no_days
        today_datetime=datetime.now()+timedelta(days=days)
        service_ids=self.env['kts.service.management'].search([('state','=','plan'),('due_date','<=',today_datetime)])
        for line in service_ids:
            if line.state=='plan':
                line.write({'state':'new'})
            
class kts_contract_report(models.Model):
    _name='kts.contract.report'
    
    def get_val_recs(self):
        move_lines=[]
        if self.report_type=='amc_end_register':
           move_lines=self.amc_end_register()
        elif self.report_type=='product_amc_register':       
             move_lines=self.product_amc_register()
        elif self.report_type=='product_end_register':       
             move_lines=self.product_end_register()
        elif self.report_type=='master_contract_report':       
             move_lines=self.master_contract_report()
        elif self.report_type=='contract_report':       
             move_lines=self.contract_report()
        
        return move_lines
   
    def _get_report_type(self):
        report_type=[]
        report_type.append(('amc_end_register','AMC END Register'))
        report_type.append(('product_amc_register','Product and AMC Register'))
        report_type.append(('product_end_register','Product End Register'))
        report_type.append(('master_contract_report','Master Contract Report'))
        report_type.append(('contract_report','Contract Report'))
        
        return report_type
    
    name=fields.Char('Name')
    date_start= fields.Date('Start Date',)
    date_stop= fields.Date('End Date')
    report_type=fields.Selection(_get_report_type, string='Report Type')
    product_id = fields.Many2one('product.product', string='Product')
    expire = fields.Selection([('monthly','Monthly'),('quat','Quarterly')],string="Expire On",default='monthly',)
    team_id = fields.Many2one('crm.team', string='Sales Team')
    sale_id=fields.Many2one('sale.order',string='Sale Order')
    _defaults = {
                       'out_format' : lambda *a: pdf_id,   
                  }
    @api.model
    def update_name(self,vals):
        expire=''
        if vals.get('report_type'):
           name = vals['report_type'].replace('_',' ')
           date = fields.Datetime.now()
           if vals.get('expire'):  
              expire= 'quarterly' if vals['expire']=='quat' else vals['expire'] 
           name = name.title() +' '+expire.title()+' '+date
           vals.update({
                     'name':name,
                     })   
           return vals
    
    @api.model
    def create(self, vals):
        self.update_name(vals)
        return super(kts_contract_report, self).create(vals)
    
    @api.multi
    def write(self, vals):
        self.update_name(vals)
        return super(kts_contract_report, self).write(vals)
    
    def to_print_contract(self, cr, uid, ids, context={}):
        this = self.browse(cr, uid, ids, context=context) 
        if this.report_type=='amc_end_register':
            report_name= 'amc_end_register'    
            report_name1='amc_end_register'
        elif this.report_type=='product_amc_register':
             report_name='product_amc_register'    
             report_name1='product_amc_register'
        elif this.report_type=='product_end_register':
             report_name='product_end_register'    
             report_name1='product_end_register' 
        elif this.report_type=='master_contract_report':
             report_name='master_contract_report'    
             report_name1='master_contract_report'
        elif this.report_type=='contract_report':
             report_name='contract_report'    
             report_name1='contract_report'
       
        
        context.update({'this':this, 'uiModelAndReportModelSame':False})
        return do_print_setup(self,cr, uid, ids, {'name':report_name1, 'model':'kts.contract.report','report_name':report_name},
                False,False,context)
              
    def amc_end_register(self): 
          lines=[]
          expire=self.expire
          if expire=='monthly':
             self.date_start=fields.Datetime.now()
             date1=fields.Datetime.from_string(self.date_start)
             date2=date1+relativedelta(months=1)
             date2= fields.Datetime.to_string(date1)
          elif expire=='quat':
               self.date_start=fields.Datetime.now()
               date1=fields.Datetime.from_string(self.date_start)
               date2=date1+relativedelta(months=3)
               date2= fields.Datetime.to_string(date1)
     
          query = ' where a.val_duration_date between \'%s\' and \'%s\' and a.type=\'amc\'' %(self.date_start,date2) 
          if self.product_id:
              query= query+' and a.product_id=%d ' %(self.product_id.id)
          if self.team_id:
              query= query+' and  a.team_id=%d ' %(self.team_id.id)
          main_query='select a.name, b.name as team_name, a.val_duration_date, c.name, d.name_template, e.name from kts_contract_customer a left outer join crm_team b on a.team_id=b.id  left outer join product_product d on d.id=a.product_id left outer join res_partner c on c.id=a.partner_id left outer join sale_order e on e.id=a.origin'
          main_query = main_query+query
          self.env.cr.execute(main_query)
          obj = self.env.cr.fetchall()   
          for i in obj:  
               m={
                  'name':i[0],
                  'team':i[1],
                  'val_date':i[2],
                  'customer':i[3],
                  'product':i[4],
                  'origin':i[5],
                 }
               lines.append(m)
          return lines     
      
    def product_end_register(self):
          lines=[]
          expire=self.expire
          if expire=='monthly':
             self.date_start=fields.Datetime.now()
             date1=fields.Datetime.from_string(self.date_start)
             date2=date1+relativedelta(months=1)
             date2= fields.Datetime.to_string(date1)
          elif expire=='quat':
               self.date_start=fields.Datetime.now()
               date1=fields.Datetime.from_string(self.date_start)
               date2=date1+relativedelta(months=3)
               date2= fields.Datetime.to_string(date1)
          
          query = 'a.val_duration_date between \'%s\' and \'%s\' and a.type=\'warranty\'' %(self.date_start,date2) 
          if self.product_id:
              query= query+' and a.product_id=%d' %(self.product_id.id)
          
          if self.team_id:
              query= query+' and  a.team_id=%d ' %(self.team_id.id)
          
          main_query='select a.name, b.name as team_name, a.val_duration_date, c.name, d.name_template, e.name from kts_contract_customer a left outer join crm_team b on a.team_id=b.id  left outer join product_product d on d.id=a.product_id left outer join res_partner c on c.id=a.partner_id left outer join sale_order e on e.id=a.origin   where '
          main_query = main_query+query
          self.env.cr.execute(main_query)
          obj = self.env.cr.fetchall()   
          for i in obj:  
               m={
                  'name':i[0],
                  'team':i[1],
                  'val_date':i[2],
                  'customer':i[3],
                  'product':i[4],
                  'origin':i[5],
                 }
               lines.append(m)
          return lines     
      
    def product_amc_register(self): 
          lines=[]
          self.date_start=fields.Datetime.now()
          query = 'a.val_duration_date >= \'%s\''   %(self.date_start) 
          if self.product_id:
              query= query+' and a.product_id=%d' %(self.product_id.id)                  
          
          if self.team_id:
              query= query+' and  a.team_id=%d ' %(self.team_id.id)
          
          main_query='select a.name, b.name as team_name, a.val_duration_date, c.name, d.name_template, e.name as origin, a.type from kts_contract_customer a left outer join crm_team b on a.team_id=b.id  left outer join product_product d on d.id=a.product_id left outer join res_partner c on c.id=a.partner_id  left outer join sale_order e on e.id=a.origin where '
          main_query = main_query+query
          self.env.cr.execute(main_query)
          obj = self.env.cr.fetchall()   
          for i in obj:  
               m={
                  'name':i[0],
                  'team':i[1],
                  'val_date':i[2],
                  'customer':i[3],
                  'product':i[4],
                  'origin':i[5],
                  'type':i[6]
                 }
               lines.append(m)
          return lines
      
    def master_contract_report(self):
          lines=[]
          move_lines=self.env['kts.contract'].search([])
          for line in move_lines:
              lines.append({
                            'name':line.name,
                            'type':line.type,
                            'val_duration':line.val_duration,
                            'val_duration_date':line.val_duration_date,
                            'proc_visit':line.no_proac_visit,
                            'ins_visit':'Yes' if line.no_ins_visit else 'No',
                            'due_days_ins':line.due_days,
                            'free_visit':line.no_free_visit,
                            'fre_proc_visit':line.fre_pro_visit, 
                            
                        })
          
          return lines
    
    def contract_report(self):
          lines=[]
          if self.sale_id:
             move_lines=self.env['kts.contract.customer'].search([('origin','=',self.sale_id.id)])
          else:
              move_lines=self.env['kts.contract.customer'].search([])
          for line in move_lines:
              service=''
              if line.state =='act':
                  for line1 in line.service_ids:
                      service+=line1.name+' '
              else:
                  service='There is no service for this contract.Please check contract is active or cancel' 
              lines.append({
                            'name':line.name,
                            'type':line.type,
                            'service':service,
                            'customer':line.partner_id.name,
                            'product':line.product_id.name,
                            'serialno':line.lot_ids.name if line.lot_ids else '',
                            'val_duration':line.val_duration,
                            'val_duration_date':line.val_duration_date,
                            'proc_visit':line.no_proac_visit,
                            'ins_visit':'Yes' if line.no_ins_visit else 'No',
                            'due_days_ins':line.due_days,
                            'free_visit':line.no_free_visit,
                            'fre_proc_visit':line.fre_pro_visit,     
                        })
          
          return lines
                 
class kts_service_report(models.Model):
    _name='kts.service.report'
    def get_move_lines(self):
        move_obj=[]
        if self.report_type =='Service_due':     
            move_obj = self.Service_due()
        
        elif self.report_type == 'service_visit_report':
             move_obj = self.service_visit_report()
        
        elif self.report_type == 'material_consumtion_report':
             move_obj = self.material_consumtion_report()
        
        elif self.report_type == 'after_sale_service_status_report':
             move_obj = self.after_sale_service_status_report()
        
        elif self.report_type == 'visit_material_history_report':
             move_obj = self.visit_material_history_report()
        
        return move_obj
         
    
    def _get_report_type(self):
        report_type=[]
        report_type.append(('Service_due','Service Due Register'))
        report_type.append(('service_visit_report','Service Visit Report')) 
        report_type.append(('material_consumtion_report','Material Consumtion Report')) 
        report_type.append(('after_sale_service_status_report','After Sale Service Status Report')) 
        report_type.append(('visit_material_history_report','Visit Material History Report')) 
        
        return report_type
    
    name=fields.Char('Name')
    date= fields.Date('Todays Date',)
    expire=fields.Selection([('monthly','Monthly'),('quat','Quarterly')],string='Expire on')
    report_type=fields.Selection(_get_report_type, string='Report Type')
    date_start=fields.Date(string='Start Date')
    date_stop=fields.Date(string='End Date')
    service_type=fields.Selection([('install','Installation'),('proact','Proactive'),('aftersale','After Sale service')],string='Service type')
    contract_id=fields.Many2one('kts.contract.customer',string='Contract')
    partner_id=fields.Many2one('res.partner',string='Customer',domain=[('parent_id','=',False)])
    
    def to_print_service(self, cr, uid, ids, context={}):
        this = self.browse(cr, uid, ids, context=context) 
        if this.report_type == 'Service_due':
           report_name='Service_due'
           report_name1='Service Due Register'
        elif this.report_type == 'service_visit_report':
            report_name='service_visit_report'
            report_name1='Service Visit Report'
        elif this.report_type == 'material_consumtion_report':
            report_name='material_consumtion_report'
            report_name1='Material Consumtion Report'
        elif this.report_type == 'after_sale_service_status_report':
            report_name='after_sale_service_status_report'
            report_name1='After Sale Service Status Report'
        elif this.report_type == 'visit_material_history_report':
            report_name='visit_material_history_report'
            report_name1='Visit Material History Report'
            
        context.update({'this':this, 'uiModelAndReportModelSame':False})
        
        return do_print_setup(self,cr, uid, ids, {'name':report_name1, 'model':'kts.service.report','report_name':report_name},
                False,False,context)
    
    def visit_material_history_report(self):
        lines=[]
        domain=[]
        if self.contract_id:
           domain.append(('invcontract_id','=',self.contract_id.id))
        if self.partner_id:
            domain.append(('partner_id','=',self.partner_id.id))    
        move_lines=self.env['kts.service.management'].search(domain)     
        for line in move_lines:
            lines.append({
                          'main':True,
                          'contract':line.invcontract_id.name if line.invcontract_id else '',
                          'product':line.invcontract_id.product_id.name,
                          'serial':line.invcontract_id.lot_ids.name if line.invcontract_id.lot_ids else '',
                          'service':line.name,
                          'service_type':line.type,
                          'visit_line':False,
                          'material_line':False
                          })
            for line1 in line.visit_line:
                lines.append({
                              'main':False,
                              'emp':line1.emp_id.name,
                              'state':line1.state,
                              'start_date':line1.start_time,
                              'stop_date':line1.end_time,
                              'charges':line1.product_price,
                              'invoice':'Yes' if line1.invoice_flag else 'No',
                              'visit_line':True,
                              'material_line':False 
                              })
            
            for line3 in line.picking_lines:
                for line2 in line3.move_lines:
                    lines.append({
                              'main':False,
                              'material':line2.product_id.name,
                              'charges1':line2.product_id.list_price,
                              'qty':line2.product_uom_qty,
                              'invoice1':'Yes' if line1.invoice_flag else 'No',
                              'visit_line':False,
                              'material_line':True
                              })
        return lines
    
    def service_visit_report(self):
        lines=[]
        service=''
        move_lines=self.env['kts.visit.details'].search([('start_time','>=',self.date_start),('start_time','>=',self.date_stop)])
        i=0
        for line in move_lines:
            if service != line.service_management_id.name:
                service=line.service_management_id.name
                service1=service
            else:
                service1=''
            lines.append({
                          'service':service1,
                          'customer':''
                          })
            i+=1
            lines.append({
                          'sr_no':i,
                          'service':service1,
                          'customer':line.service_management_id.partner_id.name,
                          'assign':line.emp_id.name if line.emp_id else line.service_management_id.vendor_id.name,
                          'invoice':'Yes' if line.invoice_flag else 'No'
                          })     
        return lines
    
    def material_consumtion_report(self):
        lines=[]
        move_lines=self.env['stock.picking'].search([('date_done','>=',self.date_start),('date_done','<=',self.date_stop),('service_id','!=',False),('state','=','done')])
        i=0
        service=''
        for line in move_lines:
            if service != line.service_id.name:
                service = line.service_id.name
                service1 = service
            else:
                service1=''
            lines.append({
                          'service':service1,
                          'customer':''
                          })
         
            for line1 in line.move_lines:
                i+=1
                lines.append({
                          'sr_no':i,
                          'service':service1,
                          'customer':line.partner_id.name,
                          'picking':line.name,
                          'product':line1.product_id.name,
                          'qty':line1.product_uom_qty,
                          'invoice':'Yes' if line1.invoice_flag else 'No'
                          
                          })     
        
        return lines
    
    
    def Service_due(self):
          lines=[]
          if self.service_type:
              if self.service_type=='install':
                  subquery=' and a.service_type = \'installation\' '
              elif self.service_type=='proact':
                   subquery=' and a.service_type = \'maintainance\' '
              elif self.service_type=='aftersale':
                   subquery=' and a.type = \'report_customer\' '
              
          expire=self.expire
          if expire=='monthly':
              self.date=fields.Datetime.now()
              date1=fields.Datetime.from_string(self.date)
              date2=date1+relativedelta(months=1)
              date2= fields.Datetime.to_string(date1)
          elif expire=='quat':
              self.date=fields.Datetime.now()
              date1=fields.Datetime.from_string(self.date)
              date2=date1+relativedelta(months=3)
              date2= fields.Datetime.to_string(date1)
          query = ' where  a.due_date between \'%s\' and  \'%s\' and a.type=\'sys_gen\'' %(self.date,date2) 
          main_query='select a.name, b.name as customer, a.service_type, c.login as logged, a.due_date, d.name as contract from kts_service_management a left outer join res_partner b on a.partner_id=b.id left outer join res_users c on a.logged_by=c.id left outer join kts_contract_customer d on a.invcontract_id=d.id' 
          
              
          main_query = main_query+query
          if subquery:
             main_query+=subquery    
          self.env.cr.execute(main_query)
          obj = self.env.cr.fetchall()   
          for i in obj:  
                   m={
                      'name':i[0],
                      'customer':i[1],
                      'service_type':i[2],
                      'logged':i[3],
                      'due_date':i[4],
                      'contract':i[5],
                     }
                   lines.append(m)
          return lines     

    def after_sale_service_status_report(self):
        lines=[]
        move_lines=self.env['kts.service.management'].search([('type','=','report_customer'),('due_date','>=',self.date_start),('due_date','<=',self.date_stop)])               
        
        for line in move_lines:
            lines.append({
                          'service':line.name,
                          'customer':line.partner_id.name,
                          'assign':line.assigned_to.name if line.assigned_to else '',
                          'status':line.state
                          })
        return lines    
    
class kts_stock_picking_contract(models.Model):
    _inherit='stock.picking'
    service_id=fields.Many2one('kts.service.management','Service')
    service_flag=fields.Boolean(related='picking_type_id.service_flag',string='Service Flag')    
    @api.multi
    def do_new_transfer(self):
        if self.state == 'draft' or all([x.qty_done == 0.0 for x in self.pack_operation_ids]):
                # If no lots when needed, raise error
                picking_type = self.picking_type_id
                if (picking_type.use_create_lots or picking_type.use_existing_lots):
                    for pack in self.pack_operation_ids:
                        if self.product_id and self.product_id.tracking != 'none':
                            raise UserError(_('Some products require lots, so you need to specify those first!'))
        if self.picking_type_id.code=='outgoing':
           picking_obj=self
           self.env['kts.contract.customer'].contract_service_create(self) 
        res=super(kts_stock_picking_contract, self).do_new_transfer()
        return res

class kts_contract_stock_move(models.Model):
    _inherit='stock.move'
    contract_id=fields.Many2one('kts.contract',string='Contract')        
    service_flag=fields.Boolean(related='picking_type_id.service_flag',string='Service Flag')
    invoice_flag=fields.Boolean('Invoice Service',default=False)

class ProcurementOrder(models.Model):
    _inherit = "procurement.order"
    @api.model
    def _run_move_create(self, procurement):
        vals = super(ProcurementOrder, self)._run_move_create(procurement)
        if procurement.sale_line_id:
            vals.update({'contract_id': procurement.sale_line_id.contract_id.id,})   
        return vals        


class Kts_sale_make_invoice_wizard(models.Model):
    _inherit='sale.advance.payment.inv'    
    @api.multi
    def create_invoices(self):
        lines=[]
        contract_obj=self.env['kts.contract.customer']
        sale_order = self.env['sale.order'].browse(self._context.get('active_id'))
        if sale_order:
            if sale_order.order_line:
                for line in sale_order.order_line:
                    if line.product_id.type=='service':
                       if line.contract_id:
                          lines.append({
                                         'origin': sale_order.id,
                                         'partner_id': sale_order.partner_id.id,
                                         'type':line.contract_id.type,
                                         'contract_id':line.contract_id.id,
                                         'product_id': line.product_id.id,     
                                         'val_duration': line.contract_id.val_duration,
                                         'no_proac_visit':line.contract_id.no_proac_visit,
                                         'no_ins_visit': line.contract_id.no_ins_visit, 
                                         'no_free_visit':line.contract_id.no_free_visit,
                                         'fre_pro_visit':line.contract_id.fre_pro_visit,
                                         'date_creation':fields.Datetime.now(),
                                         'date_activation':fields.Datetime.now(),
                                         'team_id': sale_order.team_id.id,   
                                         'state':'inprocess',
                                         'val_duration_date':fields.Datetime.to_string(fields.Datetime.from_string(fields.Datetime.now())+relativedelta(months=line.contract_id.val_duration))
                                         })
                          for contract in lines:
                               contract_obj.create(contract)  
        res=super(Kts_sale_make_invoice_wizard, self).create_invoices()
        return res     

class kts_service_logged(models.Model):
    _name='kts.service.log.conf'
    name=fields.Char(string='Name')
    no_days=fields.Integer(string='No Of days',help='To convert service plan to logged state')
    
    
class kts_service_picking_type(models.Model):
    _inherit='stock.picking.type'
    service_flag=fields.Boolean('Service Picking',default=False)

class kts_service_account_invoice(models.Model):
    _inherit='account.invoice'
    service_id=fields.Many2one('kts.service.management',string='Service')

class kts_sale_reports_service(models.Model):
    _inherit='kts.sale.reports'
    def get_move_lines(self):
         move_obj=[]
         ret=super(kts_sale_reports_service, self).get_move_lines()
         if self.report_type =='product_contract_status_report':     
            move_obj = self.product_contract_status_report()
         elif self.report_type =='product_contract_expire_status_report':
               move_obj = self.product_contract_expire_status_report()
         elif ret:
             return ret
         return move_obj 
    
    def _get_report_type(self):
        report_type=super(kts_sale_reports_service, self)._get_report_type()
        report_type.append(('product_contract_status_report','Product Contract Status Report'),)
        report_type.append(('product_contract_expire_status_report','Product Contract Expire Status Report'),)
        
        return report_type          
    
    report_type=fields.Selection(_get_report_type, string='Report Type')
    
    def to_print_sale(self, cr, uid, ids, context={}):
        this = self.browse(cr, uid, ids, context=context)
        ret=False
        if this.report_type=='product_contract_status_report':
             report_name='product_contract_status_report'    
             report_name1='product_contract_status_report'
        elif this.report_type=='product_contract_expire_status_report':
             report_name='product_contract_expire_status_report'    
             report_name1='product_contract_expire_status_report'
        
        else:
            ret=super(kts_sale_reports_service, self).to_print_sale(cr, uid, ids, context=context)
        
        if ret:
           return ret
        else:
           context.update({'this':this, 'uiModelAndReportModelSame':False})
           return do_print_setup(self,cr, uid, ids, {'name':report_name1, 'model':'kts.sale.reports','report_name':report_name},
                False,False,context)
    
    def product_contract_status_report(self):
          lines=[]
          move_lines=self.env['product.template'].search([('contract_line_ids','!=',False)])
          i=0
          product=''
          for line in move_lines:
              for line1 in line.contract_line_ids: 
                   i+=1
                   if product != line.name:
                       product=line.name
                       product1=product
                   else:
                       product1=''    
                   lines.append({
                            
                            'product':product1,
                            'name':'',
                            
                        })
                   lines.append({
                            'sr_no':i,
                            'product':'',
                            'name':line1.contract_id.name,
                            'val_duration_date':line1.val_duration_date,
                            'default': 'Yes' if line1.default_contract else 'No'
                        })
          return lines
    
    def product_contract_expire_status_report(self):
          lines=[]
          move_lines=self.env['product.template'].search([('contract_line_ids','!=',False)])
          i=0
          product=''
          for line in move_lines:
              for line1 in line.contract_line_ids: 
                   i+=1
                   if product != line.name:
                       product=line.name
                       product1=product
                   else:
                       product1=''    
                   
                   lines.append({
                            'sr_no':i,
                            'product':product1,
                            'name':line1.contract_id.name,
                            'val_duration_date':line1.val_duration_date,
                            'default': 'Yes' if line1.default_contract else 'No'
                        })
          return lines
          

# class kts_report_action_xml_contract_service(models.Model):
#       _inherit='ir.actions.report.xml'
#        
#       def get_report_keys(self, cr, uid, ids, context):
#             report_keys=super(kts_report_action_xml_contract_service, self).get_report_keys(cr, uid, ids, context=context)
#             report_keys.append({'name':'contract', 'report_sxw_content_data':'contract','model':'kts.contract.report', },)                     
#             report_keys.append({'name':'product_end_register', 'report_sxw_content_data':'product_end_register','model':'kts.contract.report', },)                     
#             report_keys.append({'name':'amc_end_register', 'report_sxw_content_data':'amc_end_register','model':'kts.contract.report',  },)                     
#             report_keys.append({'name':'product_amc_register', 'report_sxw_content_data':'product_amc_register','model':'kts.contract.report', },)                     
#             report_keys.append({'name':'AMC Contract', 'report_sxw_content_data':'amc_contract','model':'kts.contract.customer',  },)                     
#             report_keys.append({'name':'Service Due Register', 'report_sxw_content_data':'service_due','model':'kts.service.report',  },)                     
#             report_keys.append({'name':'master_contract_report', 'report_sxw_content_data':'master_contract_report','model':'kts.contract.report', },)                     
#             report_keys.append({'name':'product_contract_status_report', 'report_sxw_content_data':'product_contract_status_report','model':'kts.sale.reports',  },)                     
#             report_keys.append({'name':'product_contract_expire_status_report', 'report_sxw_content_data':'product_contract_expire_status_report','model':'kts.sale.reports',  },)                     
#             report_keys.append({'name':'Service Visit Report', 'report_sxw_content_data':'service_visit_report','model':'kts.service.report',  },)                     
#             report_keys.append({'name':'Material Consumtion Report', 'report_sxw_content_data':'material_consumtion_report','model':'kts.service.report',  },)                     
#             report_keys.append({'name':'After Sale Service Status Report', 'report_sxw_content_data':'after_sale_service_status_report','model':'kts.service.report',  },)                     
#                
#             return report_keys
#                