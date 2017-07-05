from datetime import datetime, timedelta
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from openerp import models, fields, api, _
from openerp.exceptions import UserError
from openerp.osv.fields import related
from calendar import monthrange

class kts_employee_salary_exception(models.Model):
    """
    Employee Employee Salary Exception
    """
    _name='kts.employee.salary.exception'
    _description = 'KTS Employee Salary Exception'
    employee_id= fields.Many2one('hr.employee', "Employee", required=True)
    contract_id= fields.Many2one('kts.employee.contract', "Employee Contract")
    total_amount=fields.Float(related='contract_id.total_amount')
    salary_period= fields.Many2one('kts.salary.period', 'Salary Period' )
    contract_amount_line=fields.One2many('kts.employee.contract.amount', 'contract_sal_exe_id', string='Amount', nolable="1", store=True)
    start_date=fields.Date(string='Start Date')
    end_date=fields.Date(string='End Date')
    state = fields.Selection([
        ('open', 'Exception open'),
        ('close', 'Exception close'),
        ], string='Status', default='open')

    reason = fields.Selection([
        ('contract_exception', 'Contract not available'),
        ('contract_expired', 'Contract expired'),
        ], string='Exception Details')

    @api.onchange('contract_id')
    def onchange_contract_id(self):
        if self.contract_id:
            self.update({'contract_amount_line':self.contract_id.contract_amount_line.ids})
            return {'domain':{'contract_amount_line':[('id','in',self.contract_id.contract_amount_line.ids)]}}
            
    @api.multi
    def kts_regenerate_slip(self):
        self.ensure_one()
        res={}
        val={}
        contract_amount_line=[]
        if not self.contract_id:
            raise UserError(_('Please first create employee contract.'))
        
        if self.total_amount:
            for line in self.contract_amount_line:
                calc_amount=(line.base_rule_id.dependant_value * self.total_amount)/100
                if line.base_rule_id.deduct_contribute and line.base_rule_id.deduct_contribute=='deduct':
                    calc_amount=-calc_amount
                line.update({
                            'base_amount': calc_amount,
                            
                             })                
    
        elif not self.total_amount:
            for line in self.contract_amount_line:
                if line.base_rule_id.contribution_type!='base':
                   for line1 in self.contract_amount_line:
                       if line.base_rule_id.dependant_id.id == line1.base_rule_id.id:
                           amount=line1.base_amount
                       else:
                           continue    
                        
                   calc_amount=(line.base_rule_id.dependant_value * amount)/100
                   if line.base_rule_id.deduct_contribute and line.base_rule_id.deduct_contribute=='deduct':
                      calc_amount=-calc_amount
                else:
                    continue
                line.update({
                            'base_amount': calc_amount,
                             })                            
        for i in self.contract_amount_line:
            contract_amount_line.append({
                                         'base_rule_id':i.base_rule_id.id,
                                         'base_amount':i.base_amount,
                                         'sys_gen_amount':i.base_amount,
                                         'contract_id':self.contract_id.id,
                                         'start_date':self.salary_period.start_date,
                                         'end_date':self.salary_period.end_date,
                                         
                                         })    
                                             
        res.update({
                      'employee_id':self.employee_id.id,
                      'contract_id':self.contract_id.id,
                      'start_date':self.salary_period.start_date,
                      'end_date':self.salary_period.end_date,
                      'state':'draft',   
                      'contract_amount_line':[(0,0,tmp) for tmp in contract_amount_line ]
                        })
        self.env['kts.employee.salary'].create(res) 
            
        self.write({'state':'close'})
                
                     
               
class kts_salary_period(models.Model):
    """
    Employee Salary Period
    """
    _name='kts.salary.period'
    _description = 'KTS Salary Period'
    name=fields.Char('Name', size=64)
    start_date=fields.Date(string='Start Date')
    end_date=fields.Date(string='End Date')
    salary_generation_ids=fields.One2many('kts.employee.salary.generation', 'salary_period', string='', nolable="1")
    period=fields.Boolean(string='Salary Generated Period')
    monthly_flag=fields.Boolean(string='Monthly')
    quarterly_flag=fields.Boolean(string='Quarterly')
    semiyearly_flag=fields.Boolean(string='Semiyearly')
    yearly_flag=fields.Boolean(string='Yearly')

class kts_employee_salary_generation(models.Model):
    """
    Employee Salary Generation
    """
    _name='kts.employee.salary.generation'
    _description = 'KTS Employee Salary Generation'
    name=fields.Char('Name', size=64, required=True)
    salary_period= fields.Many2one('kts.salary.period', 'Salary Period', domain=[('period','=',False)], index=True, ondelete='cascade' )
    slip_ids=fields.One2many('kts.employee.salary', 'salary_generation_id', string='Salary Slip', nolable="1", copy=True)
    generated=fields.Boolean(related='salary_period.period')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ], string='Status', default='draft')
    
    @api.multi
    def kts_generate_slip(self):
        self.ensure_one()
        val=[]
        if self.salary_period:
           if self.salary_period.period==False:
            emp_ids=self.env['hr.employee'].search([])            
            slip_id = self.slip_ids.browse([])
            
            for emp in emp_ids:
                slip_id1=''
                emp_contract=self.env['kts.employee.contract'].search([('employee_id','=',emp.id)],order='id asc')
            
                if emp_contract and len(emp_contract)>1:
                    line=[]
                    for contract in emp_contract:
                        if contract.start_date <=self.salary_period.start_date and contract.end_date <= self.salary_period.end_date:
                           for i in contract.contract_amount_line:
                               line.append({
                                        'base_rule_id':i.base_rule_id.id,
                                        'base_amount':i.base_amount,
                                        'sys_gen_amount':i.base_amount,
                                        'contract_id':contract.id,
                                        'start_date':contract.start_date,
                                        'end_date':contract.end_date,
                                        })
                        
                        elif contract.start_date >=self.salary_period.start_date:
                               for i in contract.contract_amount_line:
                                   line.append({
                                        'base_rule_id':i.base_rule_id.id,
                                        'base_amount':i.base_amount,
                                        'sys_gen_amount':i.base_amount,
                                        'contract_id':contract.id,
                                        'start_date':contract.start_date,
                                        'end_date':self.salary_period.end_date,
                                        })
                    res.update({
                                'employee_id':contract.employee_id.id,
                                'state':'draft',
                                'contract_amount_line':[(0,0,tmp) for tmp in line]
                                })
                    slip_id1=slip_id.create(res)
                    slip_id+=slip_id1
                    self._generate_2_base_slip_payment(slip_id1)
                       
                elif emp_contract and len(emp_contract)==1: 
                    res={}
                    if (emp_contract.start_date and emp_contract.start_date<=self.salary_period.start_date or (emp_contract.end_date and emp_contract.end_date>=self.salary_period.end_date)): 
                        line=[]
                        for i in emp_contract.contract_amount_line:
                            line.append({
                                        'base_rule_id':i.base_rule_id.id,
                                        'base_amount':i.base_amount,
                                        'sys_gen_amount':i.base_amount,
                                        'contract_id':emp_contract.id,
                                        'start_date':self.salary_period.start_date,
                                        'end_date':self.salary_period.end_date,
                                        })
                        res.update({
                                    'employee_id':emp_contract.employee_id.id,
                                    'contract_id':emp_contract.id,
                                    'start_date':self.salary_period.start_date,
                                    'end_date':self.salary_period.end_date,
                                    'state':'draft',
                                    'contract_amount_line':[(0,0,tmp) for tmp in line]
                                    })
                        slip_id1=slip_id.create(res)
                        slip_id+=slip_id1
                        self._generate_slip_payment(slip_id1)
                    else:
                        res1={}
                        res1.update({
                                    'employee_id':emp_contract.employee_id.id,
                                    'salary_period':self.salary_period.id,
                                    'start_date':self.salary_period.start_date,
                                    'end_date':self.salary_period.end_date,
                                    'reason':'contract_expired',
                                    'state':'open',
                                    
                                    })                
                        self.env['kts.employee.salary.exception'].create(res1)                                            
                       
                else:
                    res1={}
                    res1.update({
                                'employee_id':emp.id,
                                'salary_period':self.salary_period.id,
                                'start_date':self.salary_period.start_date,
                                'end_date':self.salary_period.end_date,
                                'reason':'contract_exception',
                                'state':'open',
                                })          
                    self.env['kts.employee.salary.exception'].create(res1)
            self.slip_ids=slip_id
            self.write({'state':'done'})
            self.salary_period.write({'period':True})
            return 
           else:
            raise UserError(_('Salary for This Period is generated already '))       
        else:
            raise UserError(_('Please provide period and Related User for employee to generate salary '))    
    
    @api.multi
    def _generate_slip_payment(self,slip_id1):
        self.ensure_one()
        if slip_id1:
                    if slip_id1.total_amount:
                       for line in slip_id1.contract_amount_line:
                           calc_amount=(line.base_rule_id.dependant_value * slip_id1.total_amount)/100
                           if line.base_rule_id.deduct_contribute and line.base_rule_id.deduct_contribute=='deduct':
                              calc_amount=-calc_amount
                           line.update({
                                     'base_amount': calc_amount,
                                     'sys_gen_amount':calc_amount,
                                      })            
                    elif not slip_id1.total_amount:
                             for line in slip_id1.contract_amount_line:
                                 if line.base_rule_id.contribution_type!='base':
                                    for line1 in slip_id1.contract_amount_line:
                                        if line.base_rule_id.dependant_id.id == line1.base_rule_id.id:
                                           amount=line1.base_amount
                                        else:
                                             continue                 
                                    calc_amount=(line.base_rule_id.dependant_value * amount)/100
                                    if line.base_rule_id.deduct_contribute and line.base_rule_id.deduct_contribute=='deduct':
                                       calc_amount=-calc_amount
                                 else:
                                     continue
                                 line.update({
                                        'base_amount': calc_amount,
                                        'sys_gen_amount':calc_amount,
                                       })                            
    @api.multi
    def _generate_2_base_slip_payment(self,slip_id1):
        self.ensure_one()
        if slip_id1:
            delta=(fields.Datetime.from_string(self.salary_period.end_date)-fields.Datetime.from_string(self.salary_period.start_date))
            for line in slip_id1.contract_amount_line:
                if line.total_amount:
                    amount=line.total_amount/delta.days
                    day=fields.Datetime.from_string(line.end_date)-fields.Datetime.from_string(line.start_date)
                    calc_amount=(line.base_rule_id.dependant_value * (amount*day.days))/100  
                    if line.base_rule_id.deduct_contribute and line.base_rule_id.deduct_contribute=='deduct':
                        calc_amount=-calc_amount
                    line.update({
                                'base_amount': calc_amount,
                                'sys_gen_amount':calc_amount,
                                 }) 
                elif not line.total_amount:  
                                 if line.base_rule_id.contribution_type!='base':
                                    day=fields.Datetime.from_string(line.end_date)-fields.Datetime.from_string(line.start_date)
                                    for line1 in slip_id1.contract_amount_line:
                                        if line.base_rule_id.dependant_id.id == line1.base_rule_id.id:
                                           amount=(line1.base_amount/delta.days)
                                        else:
                                             continue                 
                                    calc_amount=(line.base_rule_id.dependant_value * (amount*day.days))/100
                                    if line.base_rule_id.deduct_contribute and line.base_rule_id.deduct_contribute=='deduct':
                                       calc_amount=-calc_amount
                                 else:
                                     continue
                                 line.update({
                                        'base_amount': calc_amount,
                                        'sys_gen_amount':calc_amount,
                                       })                            
     
                    
class kts_employee_salary(models.Model):
    """
    Employee Salary Generation
    """
    @api.one
    @api.depends('contract_amount_line.base_amount')
    def _compute_amount(self):
        self.amount_total = sum(line.base_amount for line in self.contract_amount_line)
        
    
    _name='kts.employee.salary'
    _description = 'KTS Employee Salary'
    employee_id= fields.Many2one('hr.employee', "Employee", required=True)
    contract_id= fields.Many2one('kts.employee.contract', "Employee Contract",)
    struct_id=fields.Many2one('kts.payroll.structure','structure')
    total_amount=fields.Float(related='contract_id.total_amount',string='Total Amount', store=True)
    contract_amount_line=fields.One2many('kts.employee.salary.line','salary_id', string='Amount Line', copy=True)
    related_total=fields.Boolean(related='struct_id.dependant_on_total')
    start_date=fields.Date(string='Start Date')
    end_date=fields.Date(string='End Date')
    salary_generation_id=fields.Many2one('kts.employee.salary.generation', "Employee Salary", index=True, ondelete='cascade') 
    journal_id=fields.Many2one('account.journal',string='Journal')
    journal_amt_id=fields.Many2one('account.journal',string='Amount Journal', domain=[('type','=','bank')])
    amount_total = fields.Float(string='Total',
        store=True, readonly=True, compute='_compute_amount')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('post','Post'),
        ], string='Status', default='draft')
    
    @api.multi
    def get_move_line(self,line):
        self.ensure_one()
        res={}
        account_debit=line.base_rule_id.account_debit
        account_credit=line.base_rule_id.account_credit
    
    @api.multi
    def action_post_salary(self):
        self.ensure_one()
        if self.journal_amt_id and self.journal_id:
           account_move = self.env['account.move']
           res={}
           res1=[]
           debit1=credit1=0.0
           for line in self.contract_amount_line:    
               debit=credit=0.0
               account_debit=line.base_rule_id.account_debit
               account_credit=line.base_rule_id.account_credit
               if line.base_rule_id.deduct_contribute=='contribute':
                  debit=line.base_amount
                  debit1+=debit
               else:
                  credit=(-1)*line.base_amount
                  credit1+=credit
               res1.append({
                        'account_id':account_debit.id,
                        'journal_id':self.journal_id.id,
                        'debit':debit,
                        'credit':credit,
                        'date':fields.Datetime.now(),
                        'name':line.base_rule_id.name + 'Charges'
                        })
        
           if self.employee_id.user_id:
              credit=debit=0.0
              partner_id = self.employee_id.user_id.partner_id
              credit=debit1-credit1
              res1.append({
                        'account_id':partner_id.property_account_payable_id.id,
                        'journal_id':self.journal_id.id,
                        'debit':debit,
                        'credit':credit,
                        'date':fields.Datetime.now(),
                        'name':'Salary to Pay on account' 
                        })
        
              move_vals = {
                'line_ids': [(0,0,res) for res in res1],
                'journal_id':self.journal_id.id,
                'partner_id':partner_id.id,
                'date': fields.Datetime.now(),
                'narration': self.employee_id.name+' salary',
              }
              account_move.create(move_vals) 
              bank_obj=self.env['account.bank.statement']
              res.update({
                       'date':fields.Datetime.now(),
                       'ref':'Salary for employee '+self.employee_id.name,
                       'partner_id':partner_id.id,
                       'name':self.employee_id.name+' sal',
                       'amount':credit,
                       })
              bank_smt_vals = {
                            'name':self.employee_id.name+'  Salary',
                            'state':'open',
                            'journal_id':self.journal_amt_id.id,
                            'date':fields.Datetime.now(),
                            'line_ids':[(0,0,res)],
                            }
              bank_obj.create(bank_smt_vals)
              self.write({'state':'post'})
           else:
               raise UserError(_('Please create related user for Employee'))
        else:
             raise UserError(_('Please select Journal and Amount Journal'))

class kts_employee_salary_line(models.Model):
    _name='kts.employee.salary.line'
    _description = 'KTS Employee Salary Line'
    base_rule_id = fields.Many2one('kts.salary.rule', 'Base Rule',)
    base_amount = fields.Float('Amount')
    related_dependant_on_total=fields.Boolean(related='base_rule_id.dependant_on_total')
    related_calculation_type=fields.Selection(related='base_rule_id.contribution_type')
    salary_id=fields.Many2one('kts.employee.salary',index=True,ondelete='cascade')
    start_date = fields.Date('Start Date')
    end_date=fields.Date('End date')
    contract_id=fields.Many2one('kts.employee.contract','Contract')
    total_amount=fields.Float(related='contract_id.total_amount', store=True)
    register_id=fields.Many2one(related='base_rule_id.register_id', store=True)
    dependant_value=fields.Float(related='base_rule_id.dependant_value', store=True)
    sys_gen_amount=fields.Float('System Gen Amount')
class kts_employee_contract_amount(models.Model):
    """
    Employee contract based on the visa, work permits
    allows to configure different Salary structure
    """
    _name='kts.employee.contract.amount'
    _description = 'KTS Employee Contract Amount'
    base_rule_id = fields.Many2one('kts.salary.rule', 'Base Rule',)
    base_amount = fields.Float('Amount')
    related_dependant_on_total=fields.Boolean(related='base_rule_id.dependant_on_total')
    related_calculation_type=fields.Selection(related='base_rule_id.contribution_type')
    contract_id = fields.Many2one('kts.employee.contract', ondelete='cascade', index=True)
    contract_sal_id = fields.Many2one('kts.employee.salary',)
    contract_sal_exe_id = fields.Many2one('kts.employee.salary.exception',)

class kts_employee_contract(models.Model):
    """
    Employee contract based on the visa, work permits
    allows to configure different Salary structure
    """
    _name='kts.employee.contract'
    _description = 'KTS Employee Contract'
    name=fields.Char('Name', size=64)
    employee_id= fields.Many2one('hr.employee', "Employee", required=True)
    struct_id= fields.Many2one('kts.payroll.structure', 'Salary Structure')
    total_amount=fields.Float('Total Amount')
    contract_amount_line=fields.One2many('kts.employee.contract.amount', 'contract_id', string='Amount', nolable="1")
    related_total=fields.Boolean(related='struct_id.dependant_on_total')
    kts_employee_salary = fields.One2many('kts.employee.salary','contract_id',string='Employees salary',copy=True)
    start_date=fields.Date(string='Start Date')
    end_date=fields.Date(string='Stop Date')
    
    @api.model
    def create(self, vals):
        obj=super(kts_employee_contract, self).create(vals)
        contract_id=self.env['kts.employee.contract'].search([('employee_id','=',obj.employee_id.id)],order='id desc',limit=2)
        if contract_id:
           for i in contract_id:
               if obj.id==i.id:
                  continue
               else:
                  if obj.start_date<i.start_date:
                      raise UserError(_('Your trying to create contract With less than previous start date'))
                  elif i.end_date==False:
                      i.write({'end_date':obj.start_date})                
                  elif i.end_date and obj.start_date<i.end_date:
                       raise UserError(_('Previous contract is not finish yet for this employee'))
        obj.update({'name':obj.employee_id.name +'  '+ obj.start_date})                   
        return obj
    
    @api.onchange('start_date','end_date')
    def check_change(self):
        if not self.end_date and not self.start_date:
            return
        elif self.start_date and self.end_date and self.start_date > self.end_date:
               self.update({'end_date':False})
               return{'value':{'end_date':False}, 'warning':{'title':'UserError','message':'End Date should be Greater Than Start Date'}}
    
    @api.onchange('struct_id')
    def onchanage_structure(self):
        res={}
        val=[]
        if self.struct_id:
            
            contract_amount_l=self.contract_amount_line.browse([])
            for i in self.struct_id.rule_ids:
                res.update({
                            'base_rule_id':i.id,
                            })
                contract_amount_l+=contract_amount_l.create(res)
            self.contract_amount_line=contract_amount_l
            return
           
    
class kts_salary_rule_category(models.Model):
    """
    KTS HR Salary Rule Category
    """
    _name = 'kts.salary.rule.category'
    _description = 'Salary Rule Category'
    name=fields.Char('Name', required=True, readonly=False)
    code=fields.Char('Code', size=64, required=True, readonly=False)
    note= fields.Text('Description')
    company_id=fields.Many2one('res.company', 'Company', required=False)
    
class kts_payroll_structure(models.Model):
    """
    Salary structure used to defined
    - Basic
    - Allowances
    - Deductions
    """
    _name = 'kts.payroll.structure'
    _description = 'Salary Structure'
    name=fields.Char('Name', required=True)
    code=fields.Char('Reference', size=64, required=True)
    company_id=fields.Many2one('res.company', 'Company', copy=False)
    sequence=fields.Integer('Sequence', help='Use to arrange calculation sequence', )
    register_id=fields.Many2one('kts.contribution.register', 'Contribution Register', help="Eventual third party involved in the salary payment of the employees.")
    note= fields.Text('Description')
    rule_ids=fields.Many2many('kts.salary.rule','kts_payroll_structure_salary_rule_rel', string='Salary Rules', copy=True)
    dependant_on_total=fields.Boolean('Dependant on total',default=False)
    
    @api.model
    def create(self,vals):
        obj=super(kts_payroll_structure, self).create(vals)
        if obj.rule_ids:
            tmp=0
            for rule in obj.rule_ids:
                if rule.dependant_on_total==True and tmp >= 0:
                   tmp+=1
                   if obj.dependant_on_total==False:
                       obj.update({'dependant_on_total':True})
                   continue
                elif rule.dependant_on_total==False and tmp <= 0:
                     tmp-=1
                     continue
                else:
                    obj.update({'dependant_on_total':False})
                    raise UserError(_('You have selected salary rule %s  Total on depend and depend on base please change it')%(rule.name))
        else:
            raise UserError(_('Please create Salary Rules Line'))
        return obj   
     
    @api.onchange('rule_ids')
    def onchange_rule_ids(self):
        if self.rule_ids:
            tmp=0
            for rule in self.rule_ids:
                if rule.dependant_on_total==True and tmp >= 0:
                   tmp+=1
                   if self.dependant_on_total==False:
                      self.update({'dependant_on_total':True})
                   continue
                elif rule.dependant_on_total==False and tmp <= 0:
                     tmp-=1
                     if rule.dependant_id.id in self.rule_ids.ids:   
                        continue
                     else:
                       self.update({'dependant_on_total':False,'rule_ids':[]})
                       return {'value':{'dependant_on_total':False,'rule_ids':[]},'warning':{'title':'UserError','message':'Please Select Base rule for this rule'}}
                
                else:
                    self.update({'dependant_on_total':False,'rule_ids':[]})
                    return {'value':{'dependant_on_total':False,'rule_ids':[]},'warning':{'title':'UserError','message':'Please Select rules in group of(Total) and Depend On Base'}}
                    
               
                                       

class kts_contrib_register(models.Model):
    '''
    Kts Contribution Register
    '''
    _name = 'kts.contribution.register'
    _description = 'Kts Contribution Register'
    name=fields.Char('Name', required=True, readonly=False)
    note=fields.Text('Description')

class kts_salary_rule(models.Model):
    '''
    Kts Salary Rule
    '''
    _name = 'kts.salary.rule'
    name=fields.Char('Name', required=True, readonly=False)
    code=fields.Char('Code', size=64, required=True, help="The code of salary rules can be used as reference in computation of other rules. In that case, it is case sensitive.")
    sequence=fields.Integer('Sequence', required=True, help='Use to arrange calculation sequence', select=True)
    category_id=fields.Many2one('kts.salary.rule.category', 'Category')
    active=fields.Boolean('Active', help="If the active field is set to false, it will allow you to hide the salary rule without removing it.",default=True)
    appears_on_payslip=fields.Boolean('Appears on Payslip', help="Used to display the salary rule on payslip.")
    register_id=fields.Many2one('kts.contribution.register', 'Contribution Register', help="Eventual third party involved in the salary payment of the employees.")
    deduct_contribute=fields.Selection([
            ('deduct', 'Deduct'),
            ('contribute', 'Contribute'),
            ], string='Category',)
    contribution_type=fields.Selection([
            ('base', 'Base'),
            ('dependant', 'Dependant'),
            ('independant','Independant Base'),
            ('tds', 'TDS'),
            ], string='Calculation Type',)
    dependant_on_total=fields.Boolean('Dependant on total')
    dependant_value=fields.Float('Dependant value in (%)')
    dependant_id=fields.Many2one('kts.salary.rule', 'Dependant On')
    account_debit=fields.Many2one('account.account', 'Debit Account')
    account_credit=fields.Many2one('account.account', 'Creadit Account')
    frequency=fields.Selection([
            ('month', 'Monthly'),
            ('quat', 'Quarterly'),
            ('semyearly', 'Semi Yearly'),
            ('yearly', 'Yearly'),
            
            ], string='Frequency',)
    
    @api.onchange('dependant_on_total','dependant_id')
    def onchange_total_dependanat_id(self):
        if self.dependant_id:
            if self.dependant_on_total:
                self.update({'dependant_id':[],'dependant_on_total':False})
                return {'value':{'dependant_id':[],'dependant_on_total':False},
                        'warning':{'title':'UserError','message':'You can not select depened on total and Depend Rule both for salary rule'}
                        }
                
                  
   