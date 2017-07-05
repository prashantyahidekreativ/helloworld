from openerp import models, fields, api, _
from openerp.addons.ktssarg_reports.ktssarg_reports import do_print_setup

class kts_product_warranty(models.Model):
    _name='kts.warranty.type'
    name=fields.Char('Name',required=True)
    note=fields.Text('Description')

class kts_product_template_master(models.Model):
    _inherit='product.template'
    
    @api.multi
    @api.depends('qty_available','virtual_available','incoming_qty','outgoing_qty')
    def _product_available_onhand(self):
        for record in self:
            outgoing_qty=record.outgoing_qty
            qty_available=record.qty_available
            record.qty_available_hand=qty_available-outgoing_qty
        
        
    warranty_months=fields.Float('Warranty Months',default=0.0)
    type_warranty=fields.Many2one('kts.warranty.type',string='Warranty Type')
    installation_support=fields.Boolean('Installation Support',default=False)
    training_support=fields.Boolean('Training Support',default=False)
    qty_available_hand=fields.Float(compute=_product_available_onhand,string="Qty on Hand Available")
class kts_purchase_order_line_warranty(models.Model):
    _inherit='purchase.order.line' 
    warranty_months=fields.Float('Warranty Months',default=0.0)
    type_warranty=fields.Many2one('kts.warranty.type',string='Warranty Type')
    installation_support=fields.Boolean('Installation Support',default=False)
    training_support=fields.Boolean('Training Support',default=False)

    @api.onchange('product_id')
    def onchange_product_id_warranty(self):
        if self.product_id:
           self.warranty_months=self.product_id.warranty_months
           self.type_warranty=self.product_id.type_warranty
           self.installation_support=self.product_id.installation_support
           self.training_support=self.product_id.training_support
class kts_sale_order_line_gift(models.Model):
    _inherit='sale.order.line'
    gift_pack=fields.Boolean('Gift Packing',default=False) 

class kts_sale_reports_warranty(models.Model):
    _inherit='kts.sale.reports'
    def get_move_lines(self):
         move_obj=[]
         ret=super(kts_sale_reports_warranty, self).get_move_lines()
         if self.report_type =='standard_warranty_report':     
            move_obj = self.standard_warranty_report()
         elif ret:
             return ret
         return move_obj 
    
    def _get_report_type(self):
        report_type=super(kts_sale_reports_warranty, self)._get_report_type()
        report_type.append(('standard_warranty_report','Standard Warranty Report'))
        return report_type          
    
    report_type=fields.Selection(_get_report_type, string='Report Type')
    
    def to_print_sale(self, cr, uid, ids, context={}):
        this = self.browse(cr, uid, ids, context=context)
        ret=False
        if this.report_type=='standard_warranty_report':
               report_name= 'standard_warranty_report'    
               report_name1='Standard Warranty Report'
        else:
            ret=super(kts_sale_reports_warranty, self).to_print_inventory(cr, uid, ids, context=context)
        
        if ret:
           return ret
        else:
           context.update({'this':this, 'uiModelAndReportModelSame':False})
           return do_print_setup(self,cr, uid, ids, {'name':report_name1, 'model':'kts.sale.reports','report_name':report_name},
                False,False,context)
    
    def standard_warranty_report(self):
        lines=[]
        self.env.cr.execute('select a.name, ' 
        'a.warranty_months, ' 
        'b.name, ' 
        'a.installation_support, a.training_support ' 
        'from product_template a, kts_warranty_type b ' 
        'where a.type_warranty=b.id ')
        move_lines = self.env.cr.fetchall()
        i=0
        for line in move_lines:
            i+=1 
            lines.append({
                          'sr_no':i,
                          'product':line[0],
                          'warn_months':line[1],
                          'warn_type':line[2],
                          'install':'Yes' if line[3] else 'NO',
                          'train':'Yes' if line[4] else 'NO',
                          })
                    
        return lines

# class kts_report_action_xml_warranty(models.Model):
#       _inherit='ir.actions.report.xml'
#       
#       def get_report_keys(self, cr, uid, ids, context):
#           report_keys=super(kts_report_action_xml_warranty, self).get_report_keys(cr, uid, ids, context=context)
#           report_keys.append({'name':'Standard Warranty Report', 'report_sxw_content_data':'standard_warranty_report','model':'kts.sale.reports', 'deferred':'adaptive',},)                     
#                             
#           return report_keys  
#                                                  
#     