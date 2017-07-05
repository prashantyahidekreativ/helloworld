from openerp import models, fields, api,_
from openerp import exceptions, _
from openerp.exceptions import UserError, RedirectWarning, ValidationError
import openerp.addons.decimal_precision as dp
import openerp
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp.tools import float_compare, float_is_zero
from openerp.tools.translate import _
from openerp import tools, SUPERUSER_ID
from openerp.exceptions import UserError, AccessError
import re

        
class kts_stock(models.Model):
    _inherit='stock.pack.operation'
    qty_received = fields.Integer('Quantity Received',default=0)
    autoserial_lot_gen = fields.Boolean(related='product_id.serialno')
    expiry_date=fields.Date('Expiry Date')
    
    @api.multi
    def autogen_expiry_date(self):
        self.ensure_one()
        if self.pack_lot_ids:
           if self.expiry_date:
              for line in self.pack_lot_ids:
                   line.write({'expiry_date':self.expiry_date}) 
           else:
               raise UserError(_('Please Selection Expiry Date'))
        else:
            raise UserError(_('Please first Genrate serial Nos'))
    
    @api.onchange('qty_done')
    def onchange_qty_done(self):
        if self.qty_done > 1.0:
            if self.qty_done > self.product_qty:
                return{'value':{'qty_done':0.0},
                       'warning':{'title':'UserError', 'message':'Product qty done is greater than product  qty!'}   
                       }        
    
    @api.multi
    def do_reopen_form(self):
        self.ensure_one()
        data_obj = self.env['ir.model.data']
        view = data_obj.xmlid_to_res_id('stock.view_pack_operation_lot_form')
        
        return { 'type': 'ir.actions.act_window', 
                'res_model':self._name, 
                'res_id':self.id, 
                'view_type':'form', 
                'view_mode': 'form', 
                'views': [(view, 'form')],
                'view_id': view,
                'target': 'new',
                'context': self._context 
                 }
       
    @api.multi
    def autogen_serialno(self):
        self.ensure_one()
        val={}
        lot_ids=False
        self.qty_done = sum([x.qty for x in self.pack_lot_ids])
        if self.qty_received and self.product_qty >= self.qty_done and self.qty_received+self.qty_done <= self.product_qty:
            if self.product_id.serialno:
               if self.product_id.serial_sequence:
                   serial_sequence = self.product_id.serial_sequence.code
               else:
                   serial_sequence='kts.serial.no'
               spolot_obj=self.pack_lot_ids.browse([])
               for i in range(0,self.qty_received):
                   val.update({
                         'lot_name':self.env['ir.sequence'].next_by_code(serial_sequence),      
                        })
                   self.pack_lot_ids+=spolot_obj.create(val)
                   self.qty_done +=1  
               return self.do_reopen_form()
            
            else:
                raise UserError(_('Product is not serial Tracker'))
     
        else:
            raise UserError(_('Quantity are done with producing serial number'))
    
    @api.multi
    def autogen_lotno(self):
        self.ensure_one()
        val={}
        lot_ids=False
        self.qty_done = sum([x.qty for x in self.pack_lot_ids])
        if self.qty_received and self.product_qty >= self.qty_done and self.qty_received+self.qty_done <= self.product_qty:
            if self.product_id.serialno:
               spolot_obj=self.pack_lot_ids.browse([])
               val.update({
                         'lot_name':self.env['ir.sequence'].next_by_code('kts.serial.no'),     
                         'qty':self.qty_received,
                        })
               self.pack_lot_ids+=spolot_obj.new(val)
               self.qty_done = self.qty_received  
               return self.do_reopen_form()
            
            else:
                raise UserError(_('Product is not  Tracker'))
     
        else:
            raise UserError(_('Quantity are done with producing lot number number'))
    
    @api.multi
    def do_partial_plus(self):
        self.ensure_one()
        if self.product_qty >= self.qty_done and self.qty_received <= (self.product_qty-self.qty_done):   
           lines=self.pack_lot_ids.search([('qty','=',0),('operation_id','=',self.id)])   
           i=self.qty_received
           for j,line in map(None,range(1,i+1),lines):
                if j:
                      line.do_plus()
           self.write({'qty_received':0})
           return self.do_reopen_form()
        else:
            raise UserError(_('Partial Done is Error due to qty to process check is wrong Process'))

    
    @api.multi
    def do_all_plus(self):
        self.ensure_one()
        pack_lot_obj=self.env['stock.pack.operation.lot']
        if self.product_qty >0.0 and self.qty_done <= 0.0:
           line=self.pack_lot_ids
           for line in self.pack_lot_ids:
                 line.do_plus()
           return self.do_reopen_form()
        else:
            raise UserError(_('All Done is already Process'))




class kts_mrp_product_produce_final_line(models.TransientModel):
      _name='mrp.product.produce.final.line'      
      product_id= fields.Many2one('product.product', string='Product')
      lot_id1 = fields.Many2one('stock.production.lot', string='Lot')
      produce_final_id= fields.Many2one('mrp.product.produce', string="Produce Final")



class kts_production_wizard(models.TransientModel):
    _inherit='mrp.product.produce'  
    lot_id= fields.Many2one('stock.production.lot', 'Lot',required=False)
    final_ids=fields.One2many('mrp.product.produce.final.line','produce_final_id',string='Serial Numbers')
    
    @api.multi
    def do_reopen_form(self):
        self.ensure_one()
        return { 'type': 'ir.actions.act_window', 
                'res_model':self._name, 
                'res_id':self.id, 
                'view_type':'form', 
                'view_mode': 'form', 
                'target': 'new',
                'context': self._context, 
                'tag':'reload' 
                 } 
    @api.multi
    def autogen_serialno(self):
        self.ensure_one()
        val1=[]
        if self.product_qty > 0.00:
            raise UserError('Please confirm it directly')
        
        if self.product_id.serialno:
            if self.product_id.serial_sequence:
                 serial_sequence = self.product_id.serial_sequence.code
            else:
                 serial_sequence='kts.serial.no'
               
            spolot_obj=self.final_ids.browse([])
            qty=int(self.product_qty)
            for i in range(1,qty+1):
                   val1=[]
                   lot_id=self.env['stock.production.lot'].create({
                             'name':self.env['ir.sequence'].next_by_code(serial_sequence),     
                             'product_id':self.product_id.id,
                           })
                 
                   val2={
                                'product_id':self.product_id.id,
                                'lot_id1':lot_id.id,                           
                                'produce_final_id':self.id
                                }
                   self.final_ids+=spolot_obj.new(val2)
            
            return self.do_reopen_form()
        else:
            raise UserError(_('Product is not serial Tracker'))
    
    @api.multi
    def do_produce(self):
        self.ensure_one()
        val1=[]
        lot_id1=[]
        production_id = self.env.context.get('active_id', False)
        production_obj=self.env['mrp.production'].browse(production_id)
        if not production_obj.jobcard_printed:
            raise UserError(_('Please Print Job Card to proceed Production'))     
        
        if self.product_qty>0.00:
           if self.product_id.serialno:
              if self.product_id.serial_sequence:
                  serial_sequence = self.product_id.serial_sequence.code
              else:
                  serial_sequence='kts.serial.no'
               
              spolot_obj=self.final_ids.browse([])
              qty=int(self.product_qty)
              product_id=self.product_id.id
              for i in range(1,qty+1):
                   lot_id=self.env['stock.production.lot'].create({
                             'name':self.env['ir.sequence'].next_by_code(serial_sequence),     
                             'product_id':product_id,
                           })
                   lot_id1.append(lot_id.id)
                                  
           else:
               raise UserError(_('Product is not serial Tracker'))
        production_id = self.env.context.get('active_id', False)
        assert production_id, "Production Id should be specified in context as a Active ID."
        data = self
        self.env['mrp.production'].action_produce(production_id,
                            data.product_qty, data.mode,lot_id1, data)
      
        return {}
 
       
class kts_mrp_production(models.Model):
     _inherit = 'mrp.production'
     
     @api.model
     def default_get(self, fields):
        if self._context:  
           res = super(kts_mrp_production, self).default_get(fields)
           default_prod_fin_loc=self.env['stock.location'].search([('default_prod_loc','=',True)])
           res.update({
                       'location_dest_id':default_prod_fin_loc[0].id,
                       })
           return res
     
     @api.depends('move_lines2')
     @api.one
     def _check_consume_line(self):
         if self._context:
            if self.move_lines2.ids:
                self.m=True
            else:
                 self.product_consumed_flag=False
     
     @api.depends('move_created_ids2')
     @api.one
     def _check_produce_line(self):
         if self._context:
            if self.move_created_ids2.ids:
               self.mrp_progress=sum(res.product_uom_qty for res in self.move_created_ids2)   
            else:
               self.mrp_progress=0.0         
     
     location_src_id=fields.Many2one('stock.location', states={'draft': [('readonly', True)]})
     location_dest_id=fields.Many2one('stock.location',states={'draft': [('readonly', True)]})        
     plan_qty=fields.Float('Plan Qty')
     confirmed_qty=fields.Float('confirmed Qty')
     jobcard_qty=fields.Float('JobCard Qty')
     product_consumed_flag=fields.Boolean('Comsume Line Flag',compute=_check_consume_line)
     reserve_flag=fields.Boolean('Reserve Done Flag', default=False)
     attachment_lines=fields.One2many('ir.attachment', 'res_id', string='Attachment Lines')          
     mrp_process_flag=fields.Boolean('MRP Process Flag',default=False)
     mrp_progress=fields.Float('MRP Progress',compute=_check_produce_line)
     
     def action_confirm(self):
         ret = super(kts_mrp_production, self).action_confirm()
         plan_qty=self.product_qty
         self.write({'plan_qty':plan_qty })
         return ret    
     
     def action_produce(self, cr, uid, production_id, production_qty, production_mode,lot_id1, wiz=False, context=None):
        """ To produce final product based on production mode (consume/consume&produce).
        If Production mode is consume, all stock move lines of raw materials will be done/consumed.
        If Production mode is consume & produce, all stock move lines of raw materials will be done/consumed
        and stock move lines of final product will be also done/produced.
        @param production_id: the ID of mrp.production object
        @param production_qty: specify qty to produce in the uom of the production order
        @param production_mode: specify production mode (consume/consume&produce).
        @param wiz: the mrp produce product wizard, which will tell the amount of consumed products needed
        @return: True
        """
        record = self.browse(cr, uid, production_id)
        if production_qty > record.qty_available_to_produce:
            raise UserError(_('''You cannot produce more than available to
                                produce for this order '''))
        stock_mov_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get("product.uom")
        production = self.browse(cr, uid, production_id, context=context)
        production_qty_uom = uom_obj._compute_qty(cr, uid, production.product_uom.id, production_qty, production.product_id.uom_id.id)
        precision = self.pool['decimal.precision'].precision_get(cr, uid, 'Product Unit of Measure')
        picking_move=0.0
        j=0
        for produce_product in production.move_created_ids:
            if produce_product.state in ('done', 'cancel'):
                continue
            loc_dest=produce_product.location_dest_id.id
            loc_src=produce_product.location_id.id
            price_unit=produce_product.price_unit
            product_id=produce_product.product_id.id
            main_move=produce_product.id
            dest_move_id=produce_product.move_dest_id.id   
            if produce_product.split_from: 
               loc_dest=produce_product.location_dest_id.id
               loc_src=produce_product.location_id.id
               price_unit=produce_product.price_unit
               product_id=produce_product.product_id.id
               main_move=produce_product.id
               dest_move_id=produce_product.id
               
        main_production_move = False
        if production_mode == 'consume_produce':
            # To produce remaining qty of final product
            produced_products = {}
            for produced_product in production.move_created_ids2:
                if produced_product.scrapped:
                    continue
                if not produced_products.get(produced_product.product_id.id, False):
                    produced_products[produced_product.product_id.id] = 0
                produced_products[produced_product.product_id.id] += produced_product.product_qty
            for produce_product in production.move_created_ids:
                subproduct_factor = self._get_subproduct_factor(cr, uid, production.id, produce_product.id, context=context)
                lot_id = False
                if wiz:
                    lot_id = wiz.lot_id.id
                qty = min(subproduct_factor * production_qty_uom, produce_product.product_qty) #Needed when producing more than maximum quantity
                new_moves = stock_mov_obj.action_consume(cr, uid, [produce_product.id], qty,
                                                         location_id=produce_product.location_id.id, restrict_lot_id=lot_id, context=context)
                
                stock_mov_obj.write(cr, uid, new_moves, {'production_id': production_id}, context=context)
                remaining_qty = subproduct_factor * production_qty_uom - qty
                if not float_is_zero(remaining_qty, precision_digits=precision):
                    # In case you need to make more than planned
                    #consumed more in wizard than previously planned
                    extra_move_id = stock_mov_obj.copy(cr, uid, produce_product.id, default={'product_uom_qty': remaining_qty,
                                                                                             'production_id': production_id}, context=context)
                    stock_mov_obj.action_confirm(cr, uid, [extra_move_id], context=context)
                    stock_mov_obj.action_done(cr, uid, [extra_move_id], context=context)

                if produce_product.product_id.id == production.product_id.id:
                    main_production_move = produce_product.id

        if production_mode in ['consume', 'consume_produce']:
            if wiz:
                consume_lines = []
                for cons in wiz.consume_lines:
                    consume_lines.append({'product_id': cons.product_id.id, 'lot_id': cons.lot_id.id, 'product_qty': cons.product_qty})
            else:
                consume_lines = self._calculate_qty(cr, uid, production, production_qty_uom, context=context)
            for consume in consume_lines:
                remaining_qty = consume['product_qty']
                for raw_material_line in production.move_lines:
                    if raw_material_line.state in ('done', 'cancel'):
                        continue
                    if remaining_qty <= 0:
                        break
                    if consume['product_id'] != raw_material_line.product_id.id:
                        continue
                    consumed_qty = min(remaining_qty, raw_material_line.product_qty)
                    stock_mov_obj.action_consume(cr, uid, [raw_material_line.id], consumed_qty, raw_material_line.location_id.id,
                                                 restrict_lot_id=consume['lot_id'], consumed_for=main_production_move, context=context)
                    remaining_qty -= consumed_qty
                if not float_is_zero(remaining_qty, precision_digits=precision):
                    #consumed more in wizard than previously planned
                    product = self.pool.get('product.product').browse(cr, uid, consume['product_id'], context=context)
                    extra_move_id = self._make_consume_line_from_data(cr, uid, production, product, product.uom_id.id, remaining_qty, context=context)
                    stock_mov_obj.write(cr, uid, [extra_move_id], {'restrict_lot_id': consume['lot_id'],
                                                                    'consumed_for': main_production_move}, context=context)
                    stock_mov_obj.action_done(cr, uid, [extra_move_id], context=context)

        self.message_post(cr, uid, production_id, body=_("%s produced") % self._description, context=context)

        # Remove remaining products to consume if no more products to produce
        if not production.move_created_ids and production.move_lines:
            stock_mov_obj.action_cancel(cr, uid, [x.id for x in production.move_lines], context=context)

        self.signal_workflow(cr, uid, [production_id], 'button_produce_done')
        
        if production.product_id.tracking=='serial':
           new_move = stock_mov_obj.browse(cr, uid, dest_move_id, context=context)
           picking_id=new_move.picking_id.id
           quant_ids=new_move.reserved_quant_ids.ids
           test_quant_ids=new_move.reserved_quant_ids
    
           if new_move.move_dest_id.id:
              picking_id=new_move.move_dest_id.picking_id.id
              quant_ids=new_move.quant_ids.ids
              test_quant_ids=new_move.move_dest_id.reserved_quant_ids
              dest_move_id=new_move.move_dest_id.id
           context = dict(context)
           context.update({'force_unlink': True})
           
           self.pool.get('stock.quant').unlink(cr, uid, quant_ids,context=context)
       
        vals1=[]
        if production.state=='done' or 'in_production':
           if production.product_id.tracking=='serial': 
              for lot_id in lot_id1:
                      quant_id=self.pool.get('stock.quant').create(cr, uid,{
                                                'lot_id':lot_id,
                                                'reservation_id':dest_move_id,
                                                'product_id':product_id,
                                                'qty':1.0, 
                                                'location_id':loc_dest,
                                                'cost':price_unit,
                                                'in_date':fields.Datetime.now(),
                                                'history_ids':(4,[main_move,]), 
                                                'company_id':self.pool.get('res.company')._company_default_get(cr, uid, 'stock.quant', context=context)
                                               }, context=context)
                          
                      vals1.append(quant_id) 
              for quant in vals1:
                   cr.execute('INSERT INTO stock_quant_move_rel (quant_id,move_id) VALUES (%s,%s)',(quant,main_move)) 
              if new_move.move_dest_id.id:
                  new_move.quant_ids=vals1
                  self.pool.get('stock.picking').do_unreserve(cr, uid, [picking_id], context=context) 
                  self.pool.get('stock.picking').action_assign(cr, uid, [picking_id], context=context)  
              else:
                  new_move.reserved_quant_ids=vals1
                  self.pool.get('stock.picking').do_prepare_partial(cr, uid, [picking_id], context=context)
         
        return True
     
     def action_assign(self, cr, uid, ids, context=None):
         production_obj=self.pool.get('mrp.production')
         res=super(kts_mrp_production, self).action_assign(cr, uid, ids, context)
         production=self.browse(cr, uid, ids, context=context)
         if production.product_id:
            confirmed_qty=production.product_qty
            production_obj.write(cr, uid,ids,{'confirmed_qty':confirmed_qty,'reserve_flag':True},context=context)
            if production.state in ('ready','in_production'):
                production_obj.write(cr, uid,ids,{'reserve_flag':False},context=context)
                
         
class kts_serial_tracking(models.Model):
     _name='kts.serial.tracking'
     production_id = fields.Many2one('mrp.production',string='Production No')
     finished_pro_id = fields.Many2one('product.product',string='Finish Product')
     fin_pro_uom_id = fields.Many2one('product.uom',string='Product UOM')
     fin_product_lot_id = fields.Many2one('stock.production.lot',string='Serial No')
     product_consume_line = fields.One2many('kts.serial.tracking.line','serial_track_id',string='Product Consumed',copy=True)

class kts_serial_tracking_line(models.Model):
    _name='kts.serial.tracking.line'
    serial_track_id=fields.Many2one('kts.serial.tracking',string='Serial Tracking')
    product_id = fields.Many2one('product.product',string='Product')
    product_uom_id = fields.Many2one('product.uom',string='Product UOM')
    product_lot_id = fields.Many2one('stock.production.lot',string='Serial No')

class kts_stock_location(models.Model):
    _inherit='stock.location'
    default_prod_loc=fields.Boolean('Production Finish Loc',default=False)

class kts_stock_picking_type(models.Model):
    _inherit='stock.picking.type'
    production_picking=fields.Boolean('Production Picking',default=False)

class kts_mrp_stock_move(models.Model):
    _inherit='stock.move'
    partial_job_card_qty=fields.Float('JobCard Qty',default=0.0)
    
    @api.multi
    def do_unreserve_mrp_consumelines(self):
        self.ensure_one()
        ctx=self._context
        if self.raw_material_production_id.id:
            self.write({'partial_job_card_qty': 0.0})
            self.do_unreserve()
    @api.multi
    def action_assign_mrp_consumelines(self):
        self.ensure_one()
        if self.raw_material_production_id.id:
            self.action_assign(False) 
    
    def action_confirm(self, cr, uid, ids, context=None):
        move_ids = []
        for move in self.browse(cr, uid, ids, context=context):
            #in order to explode a move, we must have a picking_type_id on that move because otherwise the move
            #won't be assigned to a picking and it would be weird to explode a move into several if they aren't
            #all grouped in the same picking.
            if not context:
                context={}
            context=dict(context)
            if move.picking_type_id.production_picking: 
                context.update({'production_picking':True})      
            if move.picking_type_id:
                move_ids.extend(self._action_explode(cr, uid, move, context=context))
            else:
                move_ids.append(move.id)

        #we go further with the list of ids potentially changed by action_explode
        return super(kts_mrp_stock_move, self).action_confirm(cr, uid, move_ids, context=context)

    
    
    def _picking_assign(self, cr, uid, move_ids, context=None):
        """Try to assign the moves to an existing picking
        that has not been reserved yet and has the same
        procurement group, locations and picking type  (moves should already have them identical)
         Otherwise, create a new picking to assign them to.
        """
        move = self.browse(cr, uid, move_ids, context=context)[0]
        pick_obj = self.pool.get("stock.picking")
        picks = pick_obj.search(cr, uid, [
                ('group_id', '=', move.group_id.id),
                ('location_id', '=', move.location_id.id),
                ('location_dest_id', '=', move.location_dest_id.id),
                ('picking_type_id', '=', move.picking_type_id.id),
                ('printed', '=', False),
                ('state', 'in', ['draft', 'confirmed', 'waiting', 'partially_available', 'assigned'])], limit=1, context=context)
        if picks and not context.get('production_picking'):
            pick = picks[0]
        else:
            values = self._prepare_picking_assign(cr, uid, move, context=context)
            pick = pick_obj.create(cr, uid, values, context=context)
        return self.write(cr, uid, move_ids, {'picking_id': pick}, context=context)


class kts_stock_move_consume(models.TransientModel):
    _inherit='stock.move.consume'
   
    @api.model
    def default_get(self, fields):
        res=super(kts_stock_move_consume, self).default_get(fields)
        if self._context.get('active_id'):
           move=self.env['stock.move'].browse(self._context.get('active_id'))
           if move.partial_job_card_qty:
              res.update({'product_qty': move.partial_job_card_qty})
        return res                 
   
    
    def do_move_consume(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        production_obj = self.pool.get('mrp.production')
        move_ids = context['active_ids']
        move = move_obj.browse(cr, uid, move_ids[0], context=context)
        production_id = move.raw_material_production_id.id
        production = production_obj.browse(cr, uid, production_id, context=context)
        precision = self.pool['decimal.precision'].precision_get(cr, uid, 'Product Unit of Measure')
        
        for data in self.browse(cr, uid, ids, context=context):
            if move.partial_job_card_qty < data.product_qty:
                raise UserError(_('Consume qty should not greater than reserve/job card qty'))
            qty = uom_obj._compute_qty(cr, uid, data['product_uom'].id, data.product_qty, data.product_id.uom_id.id)
            remaining_qty = move.product_qty - qty
            #check for product quantity is less than previously planned
            if float_compare(remaining_qty, 0, precision_digits=precision) >= 0:
                res=move_obj.action_consume(cr, uid, move_ids, qty, data.location_id.id, restrict_lot_id=data.restrict_lot_id.id, context=context)      
                move = move_obj.browse(cr, uid, move_ids[0], context=context)
                issue_qty= move.partial_job_card_qty - move.product_qty 
                move_obj.write(cr, uid, res, {'partial_job_card_qty':issue_qty}, context=context)
                move_obj.write(cr, uid, move.id, {'partial_job_card_qty':data.product_qty}, context=context)
            else:
                consumed_qty = min(move.product_qty, qty)
                new_moves = move_obj.action_consume(cr, uid, move_ids, consumed_qty, data.location_id.id, restrict_lot_id=data.restrict_lot_id.id, context=context)
                #consumed more in wizard than previously planned
                extra_more_qty = qty - consumed_qty
                #create new line for a remaining qty of the product
                extra_move_id = production_obj._make_consume_line_from_data(cr, uid, production, data.product_id, data.product_id.uom_id.id, extra_more_qty, context=context)
                move_obj.write(cr, uid, [extra_move_id], {'restrict_lot_id': data.restrict_lot_id.id},{'partial_job_card_qty':extra_more_qty}, context=context)
                move_obj.action_done(cr, uid, [extra_move_id], context=context)
        return {'type': 'ir.actions.act_window_close'}
              
        
        
class kts_change_production_qty(models.TransientModel):
    _inherit='change.production.qty'       
    
    @api.onchange('product_qty')
    def onchange_product_qty(self):
        if self._context.get('active_id'):
            mrp_order=self.env['mrp.production'].browse(self._context.get('active_id'))
            if mrp_order.partial_job_card_print:
                raise UserError(_('If you update qty your previous job cards get invalidated'))
        
        
    @api.multi
    def change_prod_qty(self):
        self.ensure_one()
        if self._context.get('active_id'):
            mrp_order=self.env['mrp.production'].browse(self._context.get('active_id'))
            if mrp_order.product_consumed_flag:
               raise UserError(_('You can not change production qty due to some products are consumed'))
            elif mrp_order.partial_job_card_print:
                 mrp_order.move_lines.write({'partial_job_card_qty':0.0})
                 mrp_order.write({'reserve_flag':False})
            res=super(kts_change_production_qty, self).change_prod_qty()
        return res 
    
class kts_stock_quant(models.Model):
    _inherit='stock.quant'
    
    def _create_account_move_line(self, cr, uid, quants, move, credit_account_id, debit_account_id, journal_id, context=None):
        #group quants by cost
        quant_cost_qty = {}
        for quant in quants:
            if quant_cost_qty.get(quant.cost):
                quant_cost_qty[quant.cost] += quant.qty
            else:
                quant_cost_qty[quant.cost] = quant.qty
        move_obj = self.pool.get('account.move')
        for cost, qty in quant_cost_qty.items():
            move_lines = self._prepare_account_move_line(cr, uid, move, qty, cost, credit_account_id, debit_account_id, context=context)
            date = context.get('force_period_date', move.date)
            ref=(move.product_id.name)+'  '+(move.picking_id.name if move.picking_id.name else '' )
            ref1=str(ref)
            new_move = move_obj.create(cr, uid, {'journal_id': journal_id,
                                      'line_ids': move_lines,
                                      'date': date,
                                      'ref': ref1}, context=context)
            move_obj.post(cr, uid, [new_move], context=context)

class kts_stock_pack_operation_lot(models.Model):
    _inherit='stock.pack.operation.lot'
    vendor_serial_no=fields.Char('Vendor Serial No')
    expiry_date=fields.Date('Expiry Date')
           
class kts_stock_production_lot(models.Model):
    _inherit='stock.production.lot'
    vendor_serial_no=fields.Char('Vendor Serial No')
                
class kts_inventory_stock_picking(models.Model):
    _inherit='stock.picking'
    
    def create_lots_for_picking(self, cr, uid, ids, context=None):
        lot_obj = self.pool['stock.production.lot']
        opslot_obj = self.pool['stock.pack.operation.lot']
        to_unlink = []
        for picking in self.browse(cr, uid, ids, context=context):
            for ops in picking.pack_operation_ids:
                for opslot in ops.pack_lot_ids:
                    if not opslot.lot_id:
                        if opslot.expiry_date:
                           expiry_date= opslot.expiry_date+' '+'00:00:00'
                        else:
                            expiry_date=opslot.expiry_date   
                        lot_id = lot_obj.create(cr, uid, {'name': opslot.lot_name, 'product_id': ops.product_id.id,'vendor_serial_no':opslot.vendor_serial_no,'life_date':expiry_date}, context=context)
                        opslot_obj.write(cr, uid, [opslot.id], {'lot_id':lot_id}, context=context)
                #Unlink pack operations where qty = 0
                to_unlink += [x.id for x in ops.pack_lot_ids if x.qty == 0.0]
        opslot_obj.unlink(cr, uid, to_unlink, context=context)
    