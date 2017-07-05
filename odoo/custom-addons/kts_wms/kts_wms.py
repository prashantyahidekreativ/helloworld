from openerp import models,fields,api,_
from openerp import exceptions, _
from openerp.exceptions import UserError, RedirectWarning, ValidationError
import openerp.addons.decimal_precision as dp
import openerp
from openerp.tools.translate import _
from openerp import tools, SUPERUSER_ID
from openerp.exceptions import UserError, AccessError
import re
from openerp.tools.float_utils import float_compare, float_round  
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from datetime import date, datetime
from openerp.addons.ktssarg_reports.ktssarg_reports import do_print_setup
from openerp.addons.report_aeroo.barcode import barcode
from openerp.api import Environment
import logging

_logger = logging.getLogger(__name__)
class kts_stock_quant_package(models.Model):
    _inherit='stock.quant.package'
    bin_id=fields.Many2one('kts.wms.bin',string='Bin')
class kts_bin_confirmation_code(models.Model):
    _name='kts.bin.confirmation.code'
    name=fields.Char('Name')
    picking_id=fields.Many2one('stock.picking',string='Picking')
    
class kts_wms_bin(models.Model):
    _name='kts.wms.bin'    
    name=fields.Char('Name')
    location_id=fields.Many2one('stock.location',string='Location')
    categ_id=fields.Many2one('product.category',string='Internal Category')
    capacity=fields.Float('Capacity',digits_compute=dp.get_precision('Product Unit of Measure'))
    note=fields.Text('Description')
    qty_bin=fields.Float('Current Product in Bin',digits_compute=dp.get_precision('Product Unit of Measure'))
    uom_id=fields.Many2one('product.uom',string="UOM")
    remaining_qty=fields.Float('Remaining Qty',digits_compute=dp.get_precision('Product Unit of Measure'),compute='_compute_remaining_qty',store=True)
    package_ids=fields.One2many('stock.quant.package','bin_id',string='Packages')
    active=fields.Boolean('Active',default=False)
    state=fields.Selection([('draft','New'),('active','Active')],string='Status',default='draft')
    bin_confirmation_code=fields.Char('Bin Confirmation Code',required=True)
    
    @api.multi
    def action_activate(self):
        self.ensure_one()
        if self.state=='draft':
           self.update({'state':'active',
                        'active':True
                        })
    
    @api.multi
    @api.depends('capacity','qty_bin')
    def _compute_remaining_qty(self):
        if self.capacity > 0.0:
           self.remaining_qty=(self.capacity-self.qty_bin)
    
    @api.multi
    def unlink(self):
        for rec in self:
            if rec.qty_bin or rec.capacity:
                raise UserError(_('You are not allow to delete Bin having Qty'))
        return super(kts_wms_bin, self).unlink()    
    
    def print_bin_code(self, cr, uid, ids, context={}):
        this = self.browse(cr, uid, ids, context=context) 
        if this.state=='active':
           report_name='bin_code'
           report_name1='Bin Code'
        else:
            raise UserError(_('Please print  Bin in active state'))
        context.update({'this':this, 'uiModelAndReportModelSame':False})
        return do_print_setup(self,cr, uid, ids, {'name':report_name1, 'model':'kts.wms.bin','report_name':report_name},
                False,False,context)
    
        

class kts_stock_location_bin(models.Model):
    _inherit='stock.location'
    bin=fields.Boolean('Bin',default=False) 


class kts_product_category_bin(models.Model):
    _inherit='product.category'
    bin_push_strategy=fields.Selection([('club','Club'),('opti','Optimise')],default='club',string='Bin Push Strategy')   

class kts_stock_quant_bin(models.Model):
    _inherit='stock.quant'
    bin_id=fields.Many2one('kts.wms.bin',string='Bin')
    bin_uom_qty=fields.Float('Bin UOM Qty',digits_compute=dp.get_precision('Product Unit of Measure'))
    
    def _quant_split(self, cr, uid, quant, qty, move=False, context=None):
        context = context or {}
        
        original_quant_qty=quant.qty
        if move:
           if move.location_dest_id.bin:    
              if quant.bin_id:
                 package_dest_id=move.linked_move_operation_ids.search([('reserved_quant_id','=',quant.id)]).operation_id.result_package_id
                 if move.product_id.tracking=='serial' or move.product_id.tracking=='lot':
                      for link_id in move.linked_move_operation_ids: 
                          for line1 in link_id:
                              for line in line1.operation_id.pack_lot_ids:
                                  if quant.lot_id.id == line.lot_id.id: 
                                     package_dest_id=line1.operation_id.result_package_id  
           
                      
                      #package_dest_id= False#[link_id[0].operation_id.result_package_id for link_id in move.linked_move_operation_ids if self.lot_id.id in [line.lot_id.id for line in link_id[0].operation_id.pack_lot_ids] ]
                 
                 if package_dest_id:
                    if self.pool.get('kts.wms.bin').search(cr,uid,{'package_ids','in',[package_dest_id.id]}): 
                       self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,quant.bin_id.id,{'qty_bin':(quant.bin_id.qty_bin-quant.bin_uom_qty),'package_ids':[(3,package_dest_id.id)]},context=context)
                    else:
                       self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,quant.bin_id.id,{'qty_bin':(quant.bin_id.qty_bin-quant.bin_uom_qty)},context=context)
                    self.write(cr, SUPERUSER_ID, quant.id, {'bin_id':False,'bin_uom_qty':0.0}, context=context)
                 else:
                    self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,quant.bin_id.id,{'qty_bin':(quant.bin_id.qty_bin-quant.bin_uom_qty)},context=context)
                    self.write(cr, SUPERUSER_ID, quant.id, {'bin_id':False,'bin_uom_qty':0.0}, context=context)        
              uom_obj = self.pool.get('product.uom') 
              bin_ids=self._get_bins(cr, uid, quant.id, move,context=context)
              qty_to_bin=qty
              new_quant_ids=[]
              quant_uom_id=quant.product_id.uom_id.id
              
              package_dest_id=move.linked_move_operation_ids.search([('reserved_quant_id','=',quant.id)]).operation_id.result_package_id
              if move.product_id.tracking=='serial' or move.product_id.tracking=='lot':
                      for link_id in move.linked_move_operation_ids: 
                          for line1 in link_id:
                              for line in line1.operation_id.pack_lot_ids:
                                  if quant.lot_id.id == line.lot_id.id: 
                                     package_dest_id=line1.operation_id.result_package_id  
           
                      #package_dest_id= False#[link_id.operation_id.result_package_id for link_id in move.linked_move_operation_ids if self.lot_id.id in [line.lot_id.id for line in link_id.operation_id.pack_lot_ids] ]
                 
              for bins in bin_ids:                
                    bin=bins['bin']
                    remaining_qty=bins['qty']
                      
                    if (qty_to_bin==0.0):
                        break
                    if remaining_qty >= qty_to_bin:
                       qty_to_quant=remaining_qty - qty_to_bin
                       
                       if bin.uom_id.id != quant_uom_id: 
                          qty_uom = uom_obj._compute_qty(cr, uid, quant_uom_id, qty_to_bin, bin.uom_id.id)
                       else:
                           qty_uom=qty_to_bin
                       
                       if move.location_id.bin:
                           if quant_uom_id != quant.bin_id.uom_id.id:
                               qty_uom1 = uom_obj._compute_qty(cr, uid, quant_uom_id, qty_to_bin, bin.uom_id.id)
                           else:
                               qty_uom1=qty_to_bin    
                               self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,quant.bin_id.id,{'qty_bin':(quant.bin_id.qty_bin-qty_uom1),},context=context)
                                             
                       self.write(cr, SUPERUSER_ID, quant.id, {'bin_id': bin.id,'qty':qty_to_bin,'bin_uom_qty':qty_uom}, context=context)          
                       if package_dest_id: 
                          self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,bin.id,{'qty_bin':(bin.qty_bin+qty_uom),'package_ids':[(4,package_dest_id)]},context=context)
                       else:
                           self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,bin.id,{'qty_bin':(bin.qty_bin+qty_uom),},context=context)
                       qty_to_bin=0.0
                    
                    elif remaining_qty > 0 and not quant.package_id and not dest_package_id:
                        bin_take_qty=remaining_qty
                        
                        if bin.uom_id.id != quant_uom_id: 
                           qty_uom = uom_obj._compute_qty(cr, uid, quant_uom_id, bin_take_qty, bin.uom_id.id)
                        else:
                            qty_uom=bin_take_qty
                        cr.execute("""SELECT move_id FROM stock_quant_move_rel WHERE quant_id = %s""", (quant.id,))
                        res = cr.fetchall()
                        
                        if move.location_id.bin:
                           if quant_uom_id != quant.bin_id.uom_id.id:
                               qty_uom1 = uom_obj._compute_qty(cr, uid, quant_uom_id, bin_take_qty, bin.uom_id.id)
                           else:
                               qty_uom1=bin_take_qty    
                               self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,quant.bin_id.id,{'qty_bin':(quant.bin_id.qty_bin-qty_uom1),},context=context)
                       
                        new_quant1 = self.copy(cr, SUPERUSER_ID, quant.id, default={'qty':bin_take_qty, 'history_ids': [(4, x[0]) for x in res],}, context=context)
                        new_quant_ids.append(new_quant1)
                        self.write(cr, SUPERUSER_ID, new_quant1, {'bin_id': bin.id,'bin_uom_qty':qty_uom}, context=context)
                        self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,bin.id,{'qty_bin':(bin.qty_bin+qty_uom)},context=context)
                        self.write(cr, SUPERUSER_ID, quant.id, {'qty':(quant.qty-bin_take_qty)}, context=context)
                        qty_to_bin-=bin_take_qty
              
              if  qty_to_bin > 0.0:
                  raise UserError(_('Please Define New Bin for products to proceed  '))  
          
           elif move.location_id.bin or (context.get('scrap') and quant.bin_id):
              rounding = move.product_id.uom_id.rounding
              quant_uom_id=move.product_id.uom_id.id
              uom_obj=self.pool.get('product.uom')
              if float_compare(abs(original_quant_qty), abs(qty), precision_rounding=rounding) <= 0: # if quant <= qty in abs, take it entirely
                 if original_quant_qty > qty:
                     bal_qty=original_quant_qty-qty
                     if quant_uom_id != quant.bin_id.uom_id.id:
                         qty_uom1 = uom_obj._compute_qty(cr, uid, quant_uom_id, bal_qty, quant_bin_id.uom_id.id) 
                         self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,quant.bin_id.id,{'qty_bin':(quant.bin_id.qty_bin-qty_uom1),},context=context)
                     else:
                        qty_uom1=bal_qty
                        self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,quant.bin_id.id,{'qty_bin':(quant.bin_id.qty_bin-qty_uom1),},context=context)
                 else:
                     bal_qty=qty
                     if quant_uom_id != quant.bin_id.uom_id.id:
                         qty_uom1 = uom_obj._compute_qty(cr, uid, quant_uom_id, bal_qty, quant.bin_id.uom_id.id) 
                         self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,quant.bin_id.id,{'qty_bin':(quant.bin_id.qty_bin-qty_uom1),},context=context)
                     else:
                        qty_uom1=bal_qty
                        self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,quant.bin_id.id,{'qty_bin':(quant.bin_id.qty_bin-qty_uom1),},context=context)
                 self.write(cr, SUPERUSER_ID, quant.id, {'bin_id': False,'bin_uom_qty':0.0}, context=context)    
                 return False
              
              qty_round = float_round(qty, precision_rounding=rounding)
              new_qty_round = float_round(original_quant_qty - qty, precision_rounding=rounding)
              # Fetch the history_ids manually as it will not do a join with the stock moves then (=> a lot faster)
              cr.execute("""SELECT move_id FROM stock_quant_move_rel WHERE quant_id = %s""", (quant.id,))
              res = cr.fetchall()
              if quant_uom_id != quant.bin_id.uom_id.id:
                  qty_uom1 = uom_obj._compute_qty(cr, uid, quant_uom_id, qty_round, quant.bin_id.uom_id.id) 
                  self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,quant.bin_id.id,{'qty_bin':(quant.bin_id.qty_bin-qty_uom1),},context=context)
              else:
                  qty_uom1=qty_round
                  self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,quant.bin_id.id,{'qty_bin':(quant.bin_id.qty_bin-qty_uom1),},context=context)
               
              new_quant = self.copy(cr, SUPERUSER_ID, quant.id, default={'qty': new_qty_round, 'history_ids': [(4, x[0]) for x in res],'bin_uom_qty':qty_uom1}, context=context)
    
              self.write(cr, SUPERUSER_ID, quant.id, {'qty': qty_round,'bin_id': False,'bin_uom_qty':0.0}, context=context)
              return False
                                             
        rounding = quant.product_id.uom_id.rounding
        if float_compare(abs(original_quant_qty), abs(qty), precision_rounding=rounding) <= 0: # if quant <= qty in abs, take it entirely
            return False
        qty_round = float_round(qty, precision_rounding=rounding)
        new_qty_round = float_round(original_quant_qty - qty, precision_rounding=rounding)
        # Fetch the history_ids manually as it will not do a join with the stock moves then (=> a lot faster)
        cr.execute("""SELECT move_id FROM stock_quant_move_rel WHERE quant_id = %s""", (quant.id,))
        res = cr.fetchall()
        new_quant = self.copy(cr, SUPERUSER_ID, quant.id, default={'qty': new_qty_round, 'history_ids': [(4, x[0]) for x in res]}, context=context)
        if not move:
           self.write(cr, SUPERUSER_ID, quant.id, {'qty': qty_round}, context=context)
        if move and move.location_dest_id.bin and new_quant_ids:
           new_quant_ids.append(quant.id)
           return self.browse(cr, uid, new_quant_ids, context=context)
        else:
            return False
    
    def quants_move(self, cr, uid, quants, move, location_to, location_from=False, lot_id=False, owner_id=False, src_package_id=False, dest_package_id=False, entire_pack=False, context=None):
        """Moves all given stock.quant in the given destination location.  Unreserve from current move.
        :param quants: list of tuple(browse record(stock.quant) or None, quantity to move)
        :param move: browse record (stock.move)
        :param location_to: browse record (stock.location) depicting where the quants have to be moved
        :param location_from: optional browse record (stock.location) explaining where the quant has to be taken (may differ from the move source location in case a removal strategy applied). This parameter is only used to pass to _quant_create if a negative quant must be created
        :param lot_id: ID of the lot that must be set on the quants to move
        :param owner_id: ID of the partner that must own the quants to move
        :param src_package_id: ID of the package that contains the quants to move
        :param dest_package_id: ID of the package that must be set on the moved quant
        """
        quants_reconcile = []
        to_move_quants = []
        self._check_location(cr, uid, location_to, context=context)
        res1=False
        
        for quant, qty in quants:
            if not quant:
                #If quant is None, we will create a quant to move (and potentially a negative counterpart too)
                quant = self._quant_create(cr, uid, qty, move, lot_id=lot_id, owner_id=owner_id, src_package_id=src_package_id, dest_package_id=dest_package_id, force_location_from=location_from, force_location_to=location_to, context=context)
            else:
                res1=self._quant_split(cr, uid, quant, qty, move, context=context)
                if res1:
                   to_move_quants.append(res1)
                else:
                   to_move_quants.append(quant)
            if res1:
                quants_reconcile.append(res1)
            else:    
                quants_reconcile.append(quant)
            #quants_reconcile.append(quant)    
        if to_move_quants:
            to_recompute_move_ids = [x.reservation_id.id for x in to_move_quants if x.reservation_id and x.reservation_id.id != move.id]
            self.move_quants_write(cr, uid, to_move_quants, move, location_to, dest_package_id, lot_id=lot_id, entire_pack=entire_pack, context=context)
            self.pool.get('stock.move').recalculate_move_state(cr, uid, to_recompute_move_ids, context=context)
        if location_to.usage == 'internal':
            # Do manual search for quant to avoid full table scan (order by id)
            cr.execute("""
                SELECT 0 FROM stock_quant, stock_location WHERE product_id = %s AND stock_location.id = stock_quant.location_id AND
                ((stock_location.parent_left >= %s AND stock_location.parent_left < %s) OR stock_location.id = %s) AND qty < 0.0 LIMIT 1
            """, (move.product_id.id, location_to.parent_left, location_to.parent_right, location_to.id))
            if cr.fetchone():
                for quant in quants_reconcile:
                    self._quant_reconcile_negative(cr, uid, quant, move, context=context)
    
    
    def _quant_create(self, cr, uid, qty, move, lot_id=False, owner_id=False, src_package_id=False, dest_package_id=False,
                      force_location_from=False, force_location_to=False, context=None):
        '''Create a quant in the destination location and create a negative quant in the source location if it's an internal location.
        '''
        if context is None:
            context = {}
        price_unit = self.pool.get('stock.move').get_price_unit(cr, uid, move, context=context)
        location = force_location_to or move.location_dest_id
        rounding = move.product_id.uom_id.rounding
        bin_obj=self.pool.get('kts.wms.bin')
        bin_id=False
        qty_uom=0.0
        vals=[]
        if context.get('bin_id'):
            bin_id=context.get('bin_id')
            if move.product_id.uom_id.id != bin_id.uom_id.id:
                qty_uom = uom_obj._compute_qty(cr, uid, move.product_id.uom_id.id, qty, bin_id.uom_id.id)
                if bin_id.remaining_qty >= qty_uom:
                   self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,bin_id.id,{'qty_bin':(bin_id.qty_bin+qty_uom),},context=context)
                else:
                    raise UserError(_('Bin Capacity is exceed'))            
            else:
                qty_uom=qty
                if bin_id.remaining_qty >= qty_uom:
                   self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,bin_id.id,{'qty_bin':(bin_id.qty_bin+qty_uom),},context=context)
                else:
                    raise UserError(_('Bin Capacity is exceed')) 
            bin_id=bin_id.id            
            
            vals.append( {
                            'product_id': move.product_id.id,
                            'location_id': location.id,
                            'qty': float_round(qty, precision_rounding=rounding),
                            'cost': price_unit,
                            'history_ids': [(4, move.id)],
                            'in_date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'company_id': move.company_id.id,
                            'lot_id': lot_id,
                            'owner_id': owner_id,
                            'package_id': dest_package_id,
                            'bin_id':bin_id,
                            'bin_uom_qty':qty_uom,
                        })
                  
        elif move.location_dest_id.bin:
             qty_to_bin=qty
             new_quant_ids=[]
             quant_uom_id=move.product_id.uom_id.id
             bin_ids=self._get_create_quant_bins(cr,uid,qty,move,dest_package_id,context=context)    
             for bins in bin_ids:
                 bin=bins['bin']
                 remaining_qty=bins['qty']
                 if (qty_to_bin==0.0):
                        break
                 if remaining_qty >= qty_to_bin:
                    qty_to_quant=remaining_qty - qty_to_bin
                    if bin.uom_id.id != quant_uom_id: 
                        qty_uom = uom_obj._compute_qty(cr, uid, quant_uom_id, qty_to_bin, bin.uom_id.id)
                    else:
                        qty_uom=qty_to_bin
                    self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,bin.id,{'qty_bin':(bin.qty_bin+qty_uom),'package_ids':[(4,dest_package_id)]},context=context)
                    
                    vals.append( {
                            'product_id': move.product_id.id,
                            'location_id': location.id,
                            'qty': float_round(qty_to_bin, precision_rounding=rounding),
                            'cost': price_unit,
                            'history_ids': [(4, move.id)],
                            'in_date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'company_id': move.company_id.id,
                            'lot_id': lot_id,
                            'owner_id': owner_id,
                            'package_id': dest_package_id,
                            'bin_id':bin.id,
                            'bin_uom_qty':qty_uom,
                        })
                    qty_to_bin=0.0
                 elif remaining_qty > 0 and not dest_package_id:
                      bin_take_qty=remaining_qty
                      if bin.uom_id.id != quant_uom_id: 
                           qty_uom = uom_obj._compute_qty(cr, uid, quant_uom_id, bin_take_qty, bin.uom_id.id)
                      else:
                           qty_uom=bin_take_qty
                      self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,bin.id,{'qty_bin':(bin.qty_bin+qty_uom)},context=context)
                      
                      vals.append( {
                            'product_id': move.product_id.id,
                            'location_id': location.id,
                            'qty': float_round(bin_take_qty, precision_rounding=rounding),
                            'cost': price_unit,
                            'history_ids': [(4, move.id)],
                            'in_date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'company_id': move.company_id.id,
                            'lot_id': lot_id,
                            'owner_id': owner_id,
                            'package_id': dest_package_id,
                            'bin_id':bin.id,
                            'bin_uom_qty':qty_uom,
                         })
                      qty_to_bin-=bin_take_qty
             if  qty_to_bin > 0.0:
                 raise UserError(_('Please Define New Bin for products to proceed  '))  
            
        else: 
            vals.append( {
                    'product_id': move.product_id.id,
                    'location_id': location.id,
                    'qty': float_round(qty, precision_rounding=rounding),
                    'cost': price_unit,
                    'history_ids': [(4, move.id)],
                    'in_date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    'company_id': move.company_id.id,
                    'lot_id': lot_id,
                    'owner_id': owner_id,
                    'package_id': dest_package_id,
                    'bin_id':bin_id,
                    'bin_uom_qty':qty_uom,
                })
        
        if move.location_id.usage == 'internal':
            #if we were trying to move something from an internal location and reach here (quant creation),
            #it means that a negative quant has to be created as well.
            negative_vals = vals.copy()
            negative_vals['location_id'] = force_location_from and force_location_from.id or move.location_id.id
            negative_vals['qty'] = float_round(-qty, precision_rounding=rounding)
            negative_vals['cost'] = price_unit
            negative_vals['negative_move_id'] = move.id
            negative_vals['package_id'] = src_package_id
            negative_quant_id = self.create(cr, SUPERUSER_ID, negative_vals, context=context)
            vals.update({'propagated_from_id': negative_quant_id})

        # In case of serial tracking, check if the product does not exist somewhere internally already
        picking_type = move.picking_id and move.picking_id.picking_type_id or False
        if lot_id and move.product_id.tracking == 'serial' and (not picking_type or (picking_type.use_create_lots or picking_type.use_existing_lots)):
            if qty != 1.0:
                raise UserError(_('You should only receive by the piece with the same serial number'))
            other_quants = self.search(cr, uid, [('product_id', '=', move.product_id.id), ('lot_id', '=', lot_id),
                                                 ('qty', '>', 0.0), ('location_id.usage', '=', 'internal')], context=context)
            if other_quants:
                lot_name = self.pool['stock.production.lot'].browse(cr, uid, lot_id, context=context).name
                raise UserError(_('The serial number %s is already in stock') % lot_name)

        #create the quant as superuser, because we want to restrict the creation of quant manually: we should always use this method to create quants
        quant_ids=[]
        for val in vals:
            quant=self.create(cr, SUPERUSER_ID, val , context=context)
            quant_ids.append(quant)
        quant_id =quant_ids
        return self.browse(cr, uid, quant_id, context=context)
    
    def quants_reserve(self, cr, uid, quants, move, link=False, context=None):
        '''This function reserves quants for the given move (and optionally given link). If the total of quantity reserved is enough, the move's state
        is also set to 'assigned'

        :param quants: list of tuple(quant browse record or None, qty to reserve). If None is given as first tuple element, the item will be ignored. Negative quants should not be received as argument
        :param move: browse record
        :param link: browse record (stock.move.operation.link)
        '''
        toreserve = []
        reserved_availability = move.reserved_availability
        #split quants if needed
        for quant, qty in quants:
            if qty <= 0.0 or (quant and quant.qty <= 0.0):
                raise UserError(_('You can not reserve a negative quantity or a negative quant.'))
            if not quant:
                continue
            self._quant_split(cr, uid, quant, qty, move, context=context)
            toreserve.append(quant.id)
            reserved_availability += quant.qty
        #reserve quants
        if toreserve:
            self.write(cr, SUPERUSER_ID, toreserve, {'reservation_id': move.id}, context=context)
        #check if move'state needs to be set as 'assigned'
        rounding = move.product_id.uom_id.rounding
        if float_compare(reserved_availability, move.product_qty, precision_rounding=rounding) == 0 and move.state in ('confirmed', 'waiting')  :
            self.pool.get('stock.move').write(cr, uid, [move.id], {'state': 'assigned'}, context=context)
        elif float_compare(reserved_availability, 0, precision_rounding=rounding) > 0 and not move.partially_available:
            self.pool.get('stock.move').write(cr, uid, [move.id], {'partially_available': True}, context=context)

    @api.multi
    def _get_bins(self,move):
        self.ensure_one()
        bins_qty_ids=[]
        dest_package_id=move.linked_move_operation_ids.search([('reserved_quant_id','=',self.id)]).operation_id.result_package_id
        
        if move.product_id.tracking=='serial' or move.product_id.tracking=='lot':
           #dest_package_id= False 
           for link_id in move.linked_move_operation_ids: 
               for line1 in link_id:
                   for line in line1.operation_id.pack_lot_ids:
                       if self.lot_id.id == line.lot_id.id: 
                          dest_package_id=line1.operation_id.result_package_id  
                       
        quant_product_uom_id=self.product_id.uom_id.id
        quant_product_category_id=self.product_id.uom_id.category_id.id
        quant_qty=self.qty
        if dest_package_id and self.env['kts.wms.bin'].search([('location_id','=',move.location_dest_id.id),('categ_id','=',move.product_id.categ_id.id),('package_ids','in',(dest_package_id.id if dest_package_id else []))]):
           bin_ids=self.env['kts.wms.bin'].search([('location_id','=',move.location_dest_id.id),('categ_id','=',move.product_id.categ_id.id),('remaining_qty','>',0.0),('package_ids','in',dest_package_id.id)]) 
        else:
           bin_ids=self.env['kts.wms.bin'].search([('location_id','=',move.location_dest_id.id),('categ_id','=',move.product_id.categ_id.id),('remaining_qty','>',0.0)])
        
        if not bin_ids:
            raise UserError(_('There is no bin to assign these qty'))
        for bin in bin_ids: 
            if bin.uom_id.category_id.id != quant_product_category_id:
                continue
            remaining_qty=bin.remaining_qty
            if bin.uom_id.id != quant_product_uom_id:
                remaining_qty=self.env['product.uom']._compute_qty(bin.uom_id.id, remaining_qty, quant_product_uom_id)
            bins_qty_ids.append({'bin':bin,
                                 'qty':remaining_qty,
                                 'name':bin.name
                                 })
        
        if bin.categ_id.bin_push_strategy=='club' and not self.package_id and not dest_package_id:
           bins_qty_ids1=sorted(bins_qty_ids, key = lambda k: (k['qty'],k['name']))
        else:
            bins_qty_ids1=sorted(bins_qty_ids, key = lambda k: (k['qty'],k['name']), reverse=True)
        return bins_qty_ids1   
    
    
    def _get_create_quant_bins(self,cr,uid,qty,move,dest_package_id=False,context=None):
        bins_qty_ids=[]
        quant_product_uom_id=move.product_id.uom_id.id
        quant_product_category_id=move.product_id.uom_id.category_id.id
        quant_qty=qty
        if dest_package_id and  self.pool.get('kts.wms.bin').search(cr,uid,[('location_id','=',move.location_dest_id.id),('categ_id','=',move.product_id.categ_id.id),('package_ids','in',dest_package_id)],context=context):
           bin_ids=self.pool.get('kts.wms.bin').search(cr,uid,[('location_id','=',move.location_dest_id.id),('categ_id','=',move.product_id.categ_id.id),('remaining_qty','>',0.0),('package_ids','in',dest_package_id)],context=context) 
        else:
           bin_ids=self.pool.get('kts.wms.bin').search(cr,uid,[('location_id','=',move.location_dest_id.id),('categ_id','=',move.product_id.categ_id.id),('remaining_qty','>',0.0)],context=context)
        
        bin_ids=self.pool.get('kts.wms.bin').browse(cr,uid,bin_ids,context=context)
        for bin in bin_ids: 
            if bin.uom_id.category_id.id != quant_product_category_id:
                continue
            remaining_qty=bin.remaining_qty
            if bin.uom_id.id != quant_product_uom_id:
                remaining_qty=self.pool.get('product.uom')._compute_qty(cr,uid,bin.uom_id.id, remaining_qty, quant_product_uom_id,context=context)
            bins_qty_ids.append({'bin':bin,
                                 'qty':remaining_qty})
        if bin.categ_id.bin_push_strategy=='club' and not dest_package_id:
           bins_qty_ids1=sorted(bins_qty_ids, key = lambda qty: qty['qty'])
        else:
            bins_qty_ids1=sorted(bins_qty_ids, key = lambda qty: qty['qty'], reverse=True)
        return bins_qty_ids1   
    
class kts_stock_inventory_bin(models.Model):
    _inherit='stock.inventory'
    
    bin_id= fields.Many2one('kts.wms.bin', 'Inventoried Bin', readonly=True, states={'draft': [('readonly', False)]}, help='Specify Bin to focus your inventory on a particular Bin.')
    
    
    def _get_inventory_lines(self, cr, uid, inventory, context=None):
        location_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        location_ids = location_obj.search(cr, uid, [('id', 'child_of', [inventory.location_id.id])], context=context)
        domain = ' location_id in %s'
        args = (tuple(location_ids),)
        if inventory.partner_id:
            domain += ' and owner_id = %s'
            args += (inventory.partner_id.id,)
        if inventory.lot_id:
            domain += ' and lot_id = %s'
            args += (inventory.lot_id.id,)
        if inventory.product_id:
            domain += ' and product_id = %s'
            args += (inventory.product_id.id,)
        if inventory.package_id:
            domain += ' and package_id = %s'
            args += (inventory.package_id.id,)
        if inventory.bin_id:
            domain += ' and package_id = %s'
            args += (inventory.package_id.id,)
        
        cr.execute('''
           SELECT product_id, sum(qty) as product_qty, location_id, bin_id, lot_id as prod_lot_id, package_id, owner_id as partner_id
           FROM stock_quant WHERE''' + domain + '''
           GROUP BY product_id, location_id, bin_id, lot_id, package_id, partner_id
        ''', args)
        vals = []
        
        for product_line in cr.dictfetchall():
            #replace the None the dictionary by False, because falsy values are tested later on
            for key, value in product_line.items():
                if not value:
                    product_line[key] = False
            product_line['inventory_id'] = inventory.id
            product_line['theoretical_qty'] = product_line['product_qty']
            if product_line['product_id']:
                product = product_obj.browse(cr, uid, product_line['product_id'], context=context)
                product_line['product_uom_id'] = product.uom_id.id
            vals.append(product_line)
        return vals
    
class kts_stock_inventory_line_bin(models.Model):
    _inherit='stock.inventory.line'
    bin_id=fields.Many2one('kts.wms.bin',string='Bin')
    #bin_qty=fields.Float('Bin Qty',digits_compute=dp.get_precision('Product Unit of Measure'))    
    
    def _get_quants(self, cr, uid, line, context=None):
        quant_obj = self.pool["stock.quant"]
        dom = [('company_id', '=', line.company_id.id), ('location_id', '=', line.location_id.id),('bin_id','=',line.bin_id.id), ('lot_id', '=', line.prod_lot_id.id),
                        ('product_id','=', line.product_id.id), ('owner_id', '=', line.partner_id.id), ('package_id', '=', line.package_id.id)]
        quants = quant_obj.search(cr, uid, dom, context=context)
        return quants
    
    def _resolve_inventory_line(self, cr, uid, inventory_line, context=None):
        stock_move_obj = self.pool.get('stock.move')
        quant_obj = self.pool.get('stock.quant')
        diff = inventory_line.theoretical_qty - inventory_line.product_qty
        if not diff:
            return
        #each theorical_lines where difference between theoretical and checked quantities is not 0 is a line for which we need to create a stock move
        vals = {
            'name': _('INV:') + (inventory_line.inventory_id.name or ''),
            'product_id': inventory_line.product_id.id,
            'product_uom': inventory_line.product_uom_id.id,
            'date': inventory_line.inventory_id.date,
            'company_id': inventory_line.inventory_id.company_id.id,
            'inventory_id': inventory_line.inventory_id.id,
            'state': 'confirmed',
            'restrict_lot_id': inventory_line.prod_lot_id.id,
            'restrict_partner_id': inventory_line.partner_id.id,
         }
        inventory_location_id = inventory_line.product_id.property_stock_inventory.id
        if diff < 0:
            #found more than expected
            vals['location_id'] = inventory_location_id
            vals['location_dest_id'] = inventory_line.location_id.id
            vals['product_uom_qty'] = -diff
        else:
            #found less than expected
            vals['location_id'] = inventory_line.location_id.id
            vals['location_dest_id'] = inventory_location_id
            vals['product_uom_qty'] = diff
        move_id = stock_move_obj.create(cr, uid, vals, context=context)
        move = stock_move_obj.browse(cr, uid, move_id, context=context)
        if diff > 0:
            domain = [('qty', '>', 0.0), ('package_id', '=', inventory_line.package_id.id), ('lot_id', '=', inventory_line.prod_lot_id.id), ('location_id', '=', inventory_line.location_id.id),('bin_id','=',inventory_line.bin_id.id)]
            preferred_domain_list = [[('reservation_id', '=', False)], [('reservation_id.inventory_id', '!=', inventory_line.inventory_id.id)]]
            quants = quant_obj.quants_get_preferred_domain(cr, uid, move.product_qty, move, domain=domain, preferred_domain_list=preferred_domain_list)
            quant_obj.quants_reserve(cr, uid, quants, move, context=context)
        elif inventory_line.package_id and inventory_line.bin_id:
            context=dict(context)
            context.update({'bin_id':inventory_line.bin_id})
            stock_move_obj.action_done(cr, uid, move_id, context=context)
            quants = [x.id for x in move.quant_ids]
            quant_obj.write(cr, uid, quants, {'package_id': inventory_line.package_id.id}, context=context)
            self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,inventory_line.bin_id.id,{'package_ids':[(4,inventory_line.package_id.id)]},context=context)
            res = quant_obj.search(cr, uid, [('qty', '<', 0.0), ('product_id', '=', move.product_id.id),
                                    ('location_id', '=', move.location_dest_id.id), ('package_id', '!=', False)], limit=1, context=context)
            if res:
                for quant in move.quant_ids:
                    if quant.location_id.id == move.location_dest_id.id: #To avoid we take a quant that was reconcile already
                        quant_obj._quant_reconcile_negative(cr, uid, quant, move, context=context)
        
        elif inventory_line.bin_id:
            context=dict(context)
            context.update({'bin_id':inventory_line.bin_id})
            stock_move_obj.action_done(cr, uid, move_id, context=context)
            quants = [x.id for x in move.quant_ids]
            quant_obj.write(cr, uid, quants, {'bin_id': inventory_line.bin_id.id}, context=context)
            self.pool.get('kts.wms.bin').write(cr, SUPERUSER_ID,inventory_line.bin_id.id,{'package_ids':[(4,inventory_line.package_id.id)]},context=context)
            
            res = quant_obj.search(cr, uid, [('qty', '<', 0.0), ('product_id', '=', move.product_id.id),
                                    ('location_id', '=', move.location_dest_id.id), ('package_id', '!=', False)], limit=1, context=context)
            if res:
                for quant in move.quant_ids:
                    if quant.location_id.id == move.location_dest_id.id: #To avoid we take a quant that was reconcile already
                        quant_obj._quant_reconcile_negative(cr, uid, quant, move, context=context)
        
        elif inventory_line.package_id:
            stock_move_obj.action_done(cr, uid, move_id, context=context)
            quants = [x.id for x in move.quant_ids]
            quant_obj.write(cr, uid, quants, {'package_id': inventory_line.package_id.id}, context=context)
            res = quant_obj.search(cr, uid, [('qty', '<', 0.0), ('product_id', '=', move.product_id.id),
                                    ('location_id', '=', move.location_dest_id.id), ('package_id', '!=', False)], limit=1, context=context)
            if res:
                for quant in move.quant_ids:
                    if quant.location_id.id == move.location_dest_id.id: #To avoid we take a quant that was reconcile already
                        quant_obj._quant_reconcile_negative(cr, uid, quant, move, context=context)
        
        
        return move_id

class kts_wms_bin_stock_picking_type(models.Model):
    _inherit='stock.picking.type'
    putaway_printing=fields.Boolean('Putway Printing Enable',default=False)

class kts_wms_bin_stock_picking(models.Model):
    _inherit='stock.picking'
    putaway_printing=fields.Boolean(related='picking_type_id.putaway_printing',string='Putaway Printing')
    bin_code_ids=fields.One2many('kts.bin.confirmation.code','picking_id',string='Bin Confirmation Code')
    
    @api.multi
    def do_new_transfer(self):
        bin_code=[]
        bin_or_code=[]
        if self.state == 'draft' or all([x.qty_done == 0.0 for x in self.pack_operation_ids]):
                # If no lots when needed, raise error
                picking_type = self.picking_type_id
                if (picking_type.use_create_lots or picking_type.use_existing_lots):
                    for pack in self.pack_operation_ids:
                        if self.product_id and self.product_id.tracking != 'none':
                            raise UserError(_('Some products require lots, so you need to specify those first!'))
            
        
        if self.putaway_printing:
           for bin_code1 in self.bin_code_ids:
               bin_code.append(bin_code1.name) 
           
           for line1 in self.pack_operation_product_ids:
                for line2 in line1.pack_lot_ids:
                     if line2.qty>0:
                        bin_id=self._get_bin_name_for_picking_list(line1,line2.lot_id)
                        bin_or_code.append(bin_id.bin_confirmation_code)     
           if not(set(bin_code) & set(bin_or_code)):
               raise UserError(_('Bin confirmation Code Does Not Match'))
        res=super(kts_wms_bin_stock_picking, self).do_new_transfer()         
        return res
   
    def put_in_pack(self, cr, uid, ids, context=None):
        stock_move_obj = self.pool["stock.move"]
        stock_operation_obj = self.pool["stock.pack.operation"]
        package_obj = self.pool["stock.quant.package"]
        stock_move_operation_link_obj=self.pool["stock.move.operation.link"]
        package_id = False
        
        for pick in self.browse(cr, uid, ids, context=context):
            operations = [x for x in pick.pack_operation_ids if x.qty_done > 0 and (not x.result_package_id)]
            if not len(set([op1.product_id.categ_id.id for op1 in operations]))==1:
               raise UserError(_('Please select product with same category'))
            pack_operation_ids = []
            for operation in operations:
                #If we haven't done all qty in operation, we have to split into 2 operation
                op = operation
                if operation.qty_done < operation.product_qty:
                    new_operation = stock_operation_obj.copy(cr, uid, operation.id, {'product_qty': operation.qty_done,'qty_done': operation.qty_done}, context=context)
                    if operation.linked_move_operation_ids:
                        for operation_link in  operation.linked_move_operation_ids[0]:
                            new_link=stock_move_operation_link_obj.copy(cr, uid, operation_link.id,{'qty':int(operation.qty_done),'operation_id':new_operation},  context=context)
                            stock_move_operation_link_obj.write(cr, uid,operation_link.id,{'qty':operation_link.qty-int(operation.qty_done)})
                    stock_operation_obj.write(cr, uid, operation.id, {'product_qty': operation.product_qty - operation.qty_done,'qty_done': 0}, context=context)
                    if operation.pack_lot_ids:
                        packlots_transfer = [(4, x.id) for x in operation.pack_lot_ids if x.qty > 0]
                        stock_operation_obj.write(cr, uid, [new_operation], {'pack_lot_ids': packlots_transfer}, context=context)

                    op = stock_operation_obj.browse(cr, uid, new_operation, context=context)
                pack_operation_ids.append(op.id)
            
            if operations:
                stock_operation_obj.check_tracking(cr, uid, pack_operation_ids, context=context)
                package_id = package_obj.create(cr, uid, {}, context=context)
                stock_operation_obj.write(cr, uid, pack_operation_ids, {'result_package_id': package_id}, context=context)
                for operation in operations:
                    move_id=set([link.move_id.id for link  in operation.linked_move_operation_ids])
                    stock_move_obj.do_unreserve(cr, uid, move_id, context=context)
                    stock_move_obj.action_assign(cr, uid, move_id, context=context)                        
            else:
                raise UserError(_('Please process some quantities to put in the pack first!'))
        return package_id
    
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
    
    def to_print_shipping_lable(self, cr, uid, ids, context={}):
        this = self.browse(cr, uid, ids, context=context) 
        if this.picking_type_id.code=='outgoing':
           report_name='shipping_label'
           report_name1='Shipping Label'
        
        context.update({'this':this, 'uiModelAndReportModelSame':False})
        return do_print_setup(self,cr, uid, ids, {'name':report_name1, 'model':'stock.picking','report_name':report_name},
                False,False,context)
    
    
    def _get_bin_name_for_picking_list(self,operation_obj,lot_obj):
        if operation_obj.linked_move_operation_ids:
            for line in operation_obj.linked_move_operation_ids:
                lot_id=False
                if lot_obj:
                    lot_id=lot_obj.id
               
                move=line.move_id
                bin_id=self.env['stock.quant'].search([('reservation_id','=',move.id),('lot_id','=',lot_id)]).bin_id
        if bin_id:
           return bin_id
        else:
            return ''           
    
    def _get_bin_name_for_picking_list1(self,operation_obj):
        if operation_obj.linked_move_operation_ids:
            for line in operation_obj.linked_move_operation_ids:
                move=line.move_id
                bin_id=self.env['stock.quant'].search([('reservation_id','=',move.id)]).bin_id
        if bin_id:
           return bin_id
        else:
            return ''           
    
    
    def shipping_label(self):
        lines=[]              
        i=0
        
        for line1 in self.pack_operation_product_ids:
            if line1.pack_lot_ids:
                for line2 in line1.pack_lot_ids:
                     if line2.qty>0:
                        i+=1
                        lines.append({
                                   'sr_no':i,
                                   'so':self.group_id.name,
                                   'receiptno':self.name,
                                   'bin':self._get_bin_name_for_picking_list(line1,line2.lot_id),
                                   'product':line1.product_id.name,
                                   'qty':line2.qty,
                                   'serial':line2.lot_id.name,
                                   'barcode':barcode.make_barcode(line2.lot_id.name),
                                   })
            else:
                if line1.qty_done > 0:
                    lines.append({
                                   'sr_no':i,
                                   'so':self.group_id.name,
                                   'receiptno':self.name,
                                   'bin':self._get_bin_name_for_picking_list1(line1),
                                   'product':line1.product_id.name,
                                   'qty':line1.qty_done,
                                   'serial':'',
                                   'barcode':'',
                                   }) 
        return lines

         
     

class kts_stock_pack_operation_lot(models.Model):
    _inherit='stock.pack.operation.lot'
    vendor_serial_no=fields.Char('Vendor Serial No')
    expiry_date=fields.Date('Expiry Date')

class kts_stock_pack_operation_bin(models.Model):
    _inherit='stock.pack.operation'
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
           
class kts_stock_production_lot(models.Model):
    _inherit='stock.production.lot'
    vendor_serial_no=fields.Char('Vendor Serial No')

class kts_inventory_reports_bin(models.Model):
    _inherit='kts.inventory.reports'    
    
    def get_move_lines(self):
         move_obj=[]
         ret=super(kts_inventory_reports_bin, self).get_move_lines()
         if self.report_type=='putaway_receipt':
              move_obj = self.putaway_receipt()
         elif self.report_type=='stock_bin':
              move_obj = self.stock_bin()
         elif self.report_type=='stock_physical_verification':
              move_obj = self.stock_physical_verification()
         elif self.report_type =='product_warranty_report':     
              move_obj = self.product_warranty_report()
         elif self.report_type =='picking_list':     
              move_obj = self.picking_list()
         elif self.report_type =='packing_list':     
              move_obj = self.packing_list()
         elif self.report_type =='product_pricelist_weigthed_cost':     
              move_obj = self.product_pricelist_weigthed_cost()
         elif self.report_type =='procurement_order_summary':     
              move_obj = self.procurement_order_summary()
         
         elif ret:
             return ret
         return move_obj 
    
    def _get_report_type(self):
        report_type=super(kts_inventory_reports_bin, self)._get_report_type()
        report_type.append(('stock_bin','Stock Bin'))
        report_type.append(('stock_physical_verification','Stock Physical Verification Report'))
        report_type.append(('putaway_receipt','Putaway Receipt'))
        report_type.append(('product_warranty_report','Product Warranty Report'))
        report_type.append(('picking_list','Picking List'))
        report_type.append(('packing_list','Packing List'))
        report_type.append(('product_pricelist_weigthed_cost','Product Pricelist Weigthed Cost'))
        report_type.append(('procurement_order_summary','Procurement Order Summary'))
            
        return report_type  
    
    report_type=fields.Selection(_get_report_type, string='Report Type')
    bin_id=fields.Many2one('kts.wms.bin',string="Bin")
    
    def to_print_inventory(self, cr, uid, ids, context={}):
        this = self.browse(cr, uid, ids, context=context)
        ret=False
        if this.report_type=='stock_bin':
           report_name= 'stock_bin'    
           report_name1='Stock Bin'
        elif this.report_type=='stock_physical_verification':
             report_name= 'stock_physical_verification'    
             report_name1='Stock Physical Verification'
        elif this.report_type=='putaway_receipt':
             report_name= 'putaway_receipt'    
             report_name1='Putaway Receipt'
        elif this.report_type=='product_warranty_report':
             report_name= 'product_warranty_report'    
             report_name1='Product Warranty Report'
        elif this.report_type=='picking_list':
             report_name= 'picking_list'    
             report_name1='Picking List'
        elif this.report_type=='packing_list':
             report_name='packing_list'    
             report_name1='Packing List' 
        elif this.report_type=='product_pricelist_weigthed_cost':
             report_name= 'product_pricelist_weigthed_cost'    
             report_name1='Product Pricelist Weigthed Cost'
        elif this.report_type=='procurement_order_summary':
             report_name= 'procurement_order_summary'    
             report_name1='Procurement Order Summary'
           
        else:
            ret=super(kts_inventory_reports_bin, self).to_print_inventory(cr, uid, ids, context=context)
        
        if ret:
           return ret
        else:
           context.update({'this':this, 'uiModelAndReportModelSame':False})
           return do_print_setup(self,cr, uid, ids, {'name':report_name1, 'model':'kts.inventory.reports','report_name':report_name},
                False,False,context)
    def procurement_order_summary(self):
        lines=[]
        date_start=self.date_start
        
        d1=date_start+' '+'00:00:00'
        d2=date_start+' '+'24:00:00'
        move_lines=self.env['procurement.order'].search([('create_date','>=',d1),('create_date','<=',d2),('state','in',('running','done','exception'))])
        i=0
        for line in move_lines:
            i+=1
            if line.purchase_id:
               lines.append({
                             'sr_no':i,
                             'name':line.origin,
                             'po':line.purchase_id.name,
                             'state':line.state,
                             'product':line.product_id.name,
                             'qty':line.product_qty,
                             'note':''
                             })
               
            elif line.state=='exception':
                    lines.append({
                                 'sr_no':i,
                                  'name':line.origin,
                                  'po':'', 
                                  'state':line.state,      
                                  'product':line.product_id.name,
                                  'qty':line.product_qty,
                                  'note':'No vendor associated to product '
                                  })
        return lines
    def product_pricelist_weigthed_cost(self):
        lines=[]
        self.env.cr.execute('select '  
                            'a.product_id, '
                            'b.name_template, ' 
                            'sum(a.qty*a.cost/a.qty), ' 
                            'min(a.qty), '
                            'max(a.qty) ' 
                            'from '
                            'stock_quant a, product_product b ' 
                            'where location_id=12 and '
                            'a.product_id=b.id group by a.product_id,b.name_template ')
        move_lines=self.env.cr.fetchall()
        i=0
        for line in move_lines:
            i+=1
            lines.append({
                         'sr_no':i,
                         'product':line[1],
                         'avg':line[2],  
                         'min':line[3],
                         'max':line[4]
                          })
        return lines
    
    def putaway_receipt(self):
        lines=[]
        i=0
        if self.bin_id:
            bin_id=self.bin_id
        package=False
        picking_move_lines=self.env['stock.picking'].search([('state','in',('partially_available','assigned')),('picking_type_id.putaway_printing','=', True)])
        for pick_line in picking_move_lines: 
            for line in pick_line.move_lines:
                if self.bin_id:
                   quant_ids=line.reserved_quant_ids.filtered(lambda record: record.bin_id == bin_id)
                else:
                    quant_ids=line.reserved_quant_ids
                for line1 in quant_ids:
                    i+=1
                    pack=''
                     
                    for line2 in line.linked_move_operation_ids:
                        if line2.operation_id.result_package_id:
                           package=line2.operation_id.result_package_id        
                    if package:
                        pack=package.name
                    lines.append({
                              'sr_no':i,
                              'po_no':line.origin,
                              'receiptno':pick_line.name,
                              'package':pack,
                              'product':line1.product_id.name,
                              'serialno':line1.lot_id.name,
                              'qty':line1.qty,
                              'uom':line1.product_id.uom_id.name,
                              'bin':line1.bin_id.name
                              })
        return lines
       
           
    def stock_bin(self):
        lines=[]
        self.env.cr.execute('select sum(COALESCE(a.qty,0)) as qty, ' 
                            'sum(case when a.reservation_id is NULL then 0 else COALESCE(a.qty,0) end) as reserve_qty, ' 
                            'a.product_id, ' 
                            'a.location_id, '
                            'd.id as uom_id, '
                            'd.name as uom, '
                            'e.name as location, '
                            'c.name as product, '
                            'f.name as bin_name, '
                            'g.name as category '
                            'from ' 
                            'stock_quant a, ' 
                            'product_product b, ' 
                            'product_template c, '
                            'product_uom d, '
                            'stock_location e, '
                            'kts_wms_bin f, '
                            'product_category g '
                            'where '
                            'a.product_id=b.id and '
                            'b.product_tmpl_id=c.id and '
                            'c.uom_id=d.id and '
                            'a.location_id=e.id and '
                            'a.bin_id=f.id and '
                            'c.categ_id=g.id and '
                            'e.bin=\'t\' '
                            'group by  a.location_id, f.id, a.product_id, e.name, d.id, d.name,c.name,g.id '
                            'order by a.location_id, f.id')
        move_lines=self.env.cr.fetchall()
        location_name=''
        bin_name=''
        i=0
        for line in move_lines:     
             i+=1
             free_qty=line[0]-line[1]
             if line[6] != location_name:
                location_name=line[6]
                location_name1=location_name
             else:
                 location_name1=''
             lines.append({
                         'location':location_name1,
                         'product':'',
                         'bin':'' 
                          })
             if line[8] != bin_name:
                bin_name=line[8]
                bin_name1=bin_name
             else:
                 bin_name1=''
             lines.append({
                         'location':'',
                         'product':'',
                         'bin':bin_name1 
                          })
                   
             
             lines.append({
                          'sr_no':i,
                          'location':'',
                          'bin':'',
                          'product':line[7],
                          'act_qty':line[0],
                          'res_qty':line[1],
                          'free_qty':free_qty,
                          'uom':line[5],
                          'categ':line[9],
                          })        
    
        return lines
    def stock_physical_verification(self):
        lines=[]
        self.env.cr.execute('select sum(COALESCE(a.qty,0)) as qty, ' 
                            'a.product_id, ' 
                            'a.location_id, '
                            'd.id as uom_id, '
                            'd.name as uom, '
                            'e.name as location, '
                            'c.name as product, '
                            'f.name as bin_name, '
                            'g.name as category '
                            'from ' 
                            'stock_quant a, ' 
                            'product_product b, ' 
                            'product_template c, '
                            'product_uom d, '
                            'stock_location e, '
                            'kts_wms_bin f, '
                            'product_category g '
                            'where '
                            'a.product_id=b.id and '
                            'b.product_tmpl_id=c.id and '
                            'c.uom_id=d.id and '
                            'a.location_id=e.id and '
                            'a.bin_id=f.id and '
                            'c.categ_id=g.id and '
                            'e.bin=\'t\' '
                            'group by  a.location_id, f.id, a.product_id, e.name, d.id, d.name,c.name,g.id '
                            'order by a.location_id, f.id')
        move_lines=self.env.cr.fetchall()
        location_name=''
        bin_name=''
        i=0
        for line in move_lines:     
             i+=1
             if line[5] != location_name:
                location_name=line[5]
                location_name1=location_name
             else:
                 location_name1=''
             lines.append({
                         'location':location_name1,
                         'product':'',
                         'bin':'' 
                          })
             if line[7] != bin_name:
                bin_name=line[7]
                bin_name1=bin_name
             else:
                 bin_name1=''
             lines.append({
                         'location':'',
                         'product':'',
                         'bin':bin_name1 
                          })
                   
             
             lines.append({
                          'sr_no':i,
                          'location':'',
                          'bin':'',
                          'product':line[6],
                          'act_qty':line[0],
                          'uom':line[4],
                          'categ':line[8],
                          })        
    
        return lines
    
    def product_warranty_report(self):
        lines=[]
        i=0
        self.env.cr.execute('select '
                            'aa.product_id, '
                            'aa.name_template, '
                            'aa.qty_sum, '
                            'aa.warranty_months, '
                            'aa.type_warranty, '
                            'aa.installation_support, '
                            'aa.training_support, '
                            'aa.location, '
                            'bb.name '
                            'from '
                            '(select '
                            'a.product_id, e.name_template, sum(qty) as qty_sum, '
                            'd.warranty_months, '
                            'd.type_warranty, '
                            'd.installation_support, '
                            'd.training_support, '
                            'f.name as location '
                            'from '
                            'stock_quant a, '
                            'stock_move b, '
                            'stock_quant_move_rel c, '
                            'purchase_order_line d, '
                            'product_product e, '
                            'stock_location f, '
                            'stock_picking g, '
                            'stock_picking_type h '
                            'where '
                            'a.id=c.quant_id and '
                            'c.move_id=b.id and '
                            'b.purchase_line_id=d.id and '
                            'a.product_id=e.id and '
                            'a.location_id=f.id and '
                            'b.picking_id=g.id and '
                            'g.picking_type_id=h.id and '
                            'h.code=\'incoming\' and '
                            'f.usage=\'internal\' '
                            'group by '
                            'a.product_id, e.name_template, d.warranty_months, d.type_warranty, d.installation_support, d.training_support, f.name ) aa '
                            'left outer join kts_warranty_type bb on aa.type_warranty=bb.id '
                            'Order by '
                            'aa.name_template, aa.location ')        
        move_lines=self.env.cr.fetchall()            
        product_name=''
        for line in move_lines:
            i+=1
            
            if line[1]!=product_name:
                product_name=line[1]
                product_name1=product_name
            else:
                product_name1=''
            
            lines.append({
                          'product':product_name1,
                          'loc':'',
                          })
            lines.append({
                          'sr_no':i,
                          'product':'',
                          'qty':line[2],
                          'loc':line[7],
                          'warn_months':line[3],
                          'warn_type':line[8],
                          'install':'Yes' if line[5]  else 'NO',
                          'train':'Yes' if line[6]  else 'NO',
                          })
        
        
        return lines    
    
    def _get_bin_name_for_picking_list(self,operation_obj, lot_obj):
        if operation_obj.linked_move_operation_ids:
            for line in operation_obj.linked_move_operation_ids:
                move=line.move_id
                lot_id=False
                if lot_obj:
                    lot_id=lot_obj.id
                bin_id=self.env['stock.quant'].search([('reservation_id','=',move.id),('lot_id','=',lot_id)]).bin_id
        if bin_id:
           return bin_id
        else:
            return ''           
    
    def _get_bin_name_for_picking_list1(self,operation_obj):
        if operation_obj.linked_move_operation_ids:
            for line in operation_obj.linked_move_operation_ids:
                move=line.move_id
                bin_id=self.env['stock.quant'].search([('reservation_id','=',move.id)]).bin_id
        if bin_id:
           return bin_id
        else:
            return ''           
    
    def picking_list(self):
        lines=[]
        picking_type_id=self.env['stock.warehouse'].search([]).pick_type_id
        picking_move_lines=self.env['stock.picking'].search([('picking_type_id','=',picking_type_id.id),('state','in',('partially_available','assigned'))])
        
        for line in picking_move_lines:
            i=0
            for line1 in line.pack_operation_product_ids:
                if line1.pack_lot_ids:
                    for line2 in line1.pack_lot_ids:
                        if line2.qty>0:
                            i+=1
                            lines.append({
                                   'sr_no':i,
                                   'so':line.group_id.name,
                                   'receiptno':line.name,
                                   'bin':self._get_bin_name_for_picking_list(line1,line2.lot_id),
                                   'product':line1.product_id.name,
                                   'qty':line2.qty,
                                   'serial':line2.lot_id.name,
                                   'barcode':barcode.make_barcode(line2.lot_id.name),
                                   })
        
                else:
                   if line1.qty_done > 0:
                      lines.append({
                                   'sr_no':i,
                                   'so':line.group_id.name,
                                   'receiptno':line.name,
                                   'bin':self._get_bin_name_for_picking_list1(line1),
                                   'product':line1.product_id.name,
                                   'qty':line1.qty_done,
                                   'serial':'',
                                   'barcode':'',
                                   }) 
        lines=sorted(lines, key = lambda k: k['bin'])
        return lines

    def get_gift_packing(self,operation_obj):
        if operation_obj.linked_move_operation_ids:
            for line in operation_obj.linked_move_operation_ids:
                move=line.move_id
            if move.move_dest_id:
                if move.move_dest_id.procurement_id and move.move_dest_id.procurement_id.sale_line_id:
                   if move.move_dest_id.procurement_id.sale_line_id.gift_pack:
                       return 'Yes' 
                   else:
                       return 'No'
    def packing_list(self):
        lines=[]
        packing_type_id=self.env['stock.warehouse'].search([]).pack_type_id
        packing_move_lines=self.env['stock.picking'].search([('picking_type_id','=',packing_type_id.id),('state','in',('partially_available','assigned'))])
        
        for line in packing_move_lines:
            i=0
            for line1 in line.pack_operation_product_ids:
                if line1.pack_lot_ids:
                   for line2 in line1.pack_lot_ids:
                        if line2.qty>0:
                           i+=1
                           lines.append({
                                   'sr_no':i,
                                   'so':line.group_id.name,
                                   'receiptno':line.name,
                                   'bin':self._get_bin_name_for_picking_list(line1,line2.lot_id),
                                   'product':line1.product_id.name,
                                   'qty':line2.qty,
                                   'serial':line2.lot_id.name,
                                   'barcode':barcode.make_barcode(line2.lot_id.name),
                                   'gift':self.get_gift_packing(line1)
                                   })
                else:
                   if line1.qty_done > 0:
                      lines.append({
                                   'sr_no':i,
                                   'so':line.group_id.name,
                                   'receiptno':line.name,
                                   'bin':self._get_bin_name_for_picking_list1(line1),
                                   'product':line1.product_id.name,
                                   'qty':line1.qty_done,
                                   'serial':'',
                                   'barcode':'',
                                   'gift':self.get_gift_packing(line1)
                                   }) 
                   
        lines=sorted(lines, key = lambda k: k['so'])
        return lines



class kts_wms_purchase_reports(models.Model):
    _inherit='kts.purchase.reports'      
    
    def get_move_lines(self):
         move_obj=[]
         ret=super(kts_wms_purchase_reports, self).get_move_lines()
         if self.report_type=='vendor_lead_time':
              move_obj = self.vendor_lead_time()
         elif self.report_type=='purchase_price_variance':
              move_obj = self.purchase_price_variance()
         elif self.report_type=='product_lead_time':
              move_obj = self.product_lead_time()
         
         elif ret:
             return ret
         return move_obj
    def _get_report_type(self):
        report_type=super(kts_wms_purchase_reports, self)._get_report_type()
        report_type.append(('vendor_lead_time','Vendor Lead Time Report'))
        report_type.append(('purchase_price_variance','Purchase Price Variance Report'))
        report_type.append(('product_lead_time','Product Lead Time Report'))
        
        return report_type  
    
    report_type=fields.Selection(_get_report_type, string='Report Type')
    
    def to_print_purchase(self, cr, uid, ids, context={}):
        this = self.browse(cr, uid, ids, context=context)
        ret=False
        if this.report_type=='vendor_lead_time':
           report_name= 'vendor_lead_time'    
           report_name1='Vendor Lead Time'  
        elif this.report_type=='purchase_price_variance':
           report_name= 'purchase_price_variance'    
           report_name1='Purchase Price Variance Report'
        elif this.report_type=='product_lead_time':
           report_name= 'product_lead_time'    
           report_name1='Product Lead Time'  
        
        else:
            ret=super(kts_wms_purchase_reports, self).to_print_purchase(cr, uid, ids, context=context)
        
        if ret:
           return ret
        else:
           context.update({'this':this, 'uiModelAndReportModelSame':False})
           return do_print_setup(self,cr, uid, ids, {'name':report_name1, 'model':'kts.purchase.reports','report_name':report_name},
                False,False,context)
    
    def vendor_lead_time(self):
        lines=[]
        self.env.cr.execute('select ' 
                            'aaa.minimum, aaa.maximum, aaa.weighted_average, bbb.name, ccc.name_template '
                            'from '
                            '(select '
                            'min(aa.difference) as minimum , max(aa.difference) as maximum, sum(aa.weighted_diff)/sum(aa.product_qty) as weighted_average,  aa.product_id, aa.partner_id '
                            'from '
                            '(select ' 
                            'to_date(to_char(a.date,\'DDMMYYYY\'),\'DDMMYYYY\') - to_date(to_char(d.date_planned,\'DDMMYYYY\'),\'DDMMYYYY\') as difference, '
                            '( to_date(to_char(a.date,\'DDMMYYYY\'),\'DDMMYYYY\') - to_date(to_char(d.date_planned,\'DDMMYYYY\'),\'DDMMYYYY\')) * a.product_qty as weighted_diff, a.product_qty, a.product_id, b.partner_id '
                            'from ' 
                            'stock_move a, '
                            'stock_picking b, '
                            'stock_picking_type c, '
                            'purchase_order_line d '
                            'where '
                            'a.picking_id=b.id and '
                            'b.picking_type_id = c.id and '
                            'c.code=\'incoming\' and '
                            'a.purchase_line_id=d.id) aa '
                            'group by   aa.product_id, aa.partner_id ) aaa, res_partner bbb, product_product ccc where aaa.partner_id=bbb.id and aaa.product_id=ccc.id ' 
                            'order by bbb.name, ccc.name_template '
                           )
        
        move_lines=self.env.cr.fetchall()
        i=0
        customer=''
        for line in move_lines:     
          
            if line[3]!=customer: 
                  customer=line[3]
                  customer1=customer
                  i=0
            else:
                 customer1=''
            lines.append({
                          'customer':customer1,
                          'product_name':'',
                            }) 
            i+=1
            lines.append({
                          'customer':'',
                          'sr_no':i,
                          'product_name':line[4],
                          'min':line[0],
                          'max':line[1],
                          'avg': line[2],
                          })
               
        return lines 
    
    def product_lead_time(self):
        lines=[]
        self.env.cr.execute('select ' 
                            'aaa.minimum, aaa.maximum, aaa.weighted_average, bbb.name, ccc.name_template '
                            'from '
                            '(select '
                            'min(aa.difference) as minimum , max(aa.difference) as maximum, sum(aa.weighted_diff)/sum(aa.product_qty) as weighted_average,  aa.product_id, aa.partner_id '
                            'from '
                            '(select ' 
                            'to_date(to_char(a.date,\'DDMMYYYY\'),\'DDMMYYYY\') - to_date(to_char(d.date_planned,\'DDMMYYYY\'),\'DDMMYYYY\') as difference, '
                            '( to_date(to_char(a.date,\'DDMMYYYY\'),\'DDMMYYYY\') - to_date(to_char(d.date_planned,\'DDMMYYYY\'),\'DDMMYYYY\')) * a.product_qty as weighted_diff, a.product_qty, a.product_id, b.partner_id '
                            'from ' 
                            'stock_move a, '
                            'stock_picking b, '
                            'stock_picking_type c, '
                            'purchase_order_line d '
                            'where '
                            'a.picking_id=b.id and '
                            'b.picking_type_id = c.id and '
                            'c.code=\'incoming\' and '
                            'a.purchase_line_id=d.id) aa '
                            'group by   aa.product_id, aa.partner_id ) aaa, res_partner bbb, product_product ccc where aaa.partner_id=bbb.id and aaa.product_id=ccc.id ' 
                            'order by ccc.name_template, bbb.name '
                           )
        
        move_lines=self.env.cr.fetchall()
        i=0
        product=''
        for line in move_lines:     
            
            if line[4]!=product: 
                  product=line[4]
                  product1=product
                  i=0
            else:
                 product1=''
            lines.append({
                          'customer':'',
                          'product_name':product1,
                            }) 
            i+=1
            lines.append({
                          'customer':line[3],
                          'sr_no':i,
                          'product_name':'',
                          'min':line[0],
                          'max':line[1],
                          'avg': line[2],
                          })
               
        return lines 
    
    def purchase_price_variance(self):
        lines=[]
        date_start=self.date_start
        date_stop=self.date_stop
        self.env.cr.execute('select '
                            'min(aa.price_unit), max(aa.price_unit), sum(aa.weighted_cost)/sum(aa.product_qty), ' 
                            'aa.product_id, aa.name_template ' 
                            'from'
                            '(select '
                            'b.product_id, b.price_unit, b.product_qty, b.product_qty*b.price_unit as weighted_cost, c.name_template '
                            'from '
                            'purchase_order a, purchase_order_line b, product_product c '
                            'where '
                            'a.id=b.order_id and '
                            'date_order between %s and %s and b.product_id=c.id) aa '
                            'group by aa.product_id, aa.name_template',(date_start,date_stop))
        move_lines=self.env.cr.fetchall()
        i=0
        for line in move_lines:
            i+=1
            lines.append({
                          'sr_no':i,
                          'product_name':line[4],
                          'min':line[0],
                          'max':line[1],
                          'avg':line[2]
                          
                          }) 
        return lines     
class kts_wms_sale_order_reports(models.Model):                                     
    _inherit='kts.sale.reports'
    
    def get_move_lines(self):
         move_obj=[]
         ret=super(kts_wms_sale_order_reports, self).get_move_lines()
         if self.report_type=='sale_order_booking_report':
              move_obj = self.sale_order_booking_report()
         elif self.report_type=='sale_order_analysis':
              move_obj = self.sale_order_analysis()
         elif self.report_type=='sale_price_variance':
              move_obj = self.sale_price_variance()
          
         elif ret:
             return ret
         return move_obj
    def _get_report_type(self):
        report_type=super(kts_wms_sale_order_reports, self)._get_report_type()
        report_type.append(('sale_order_booking_report','Sale Order Booking Report'))
        report_type.append(('sale_order_analysis','Sale Order Analysis Report'))
        report_type.append(('sale_price_variance','Sale Price Variance Report'))
        
        return report_type  
    
    report_type=fields.Selection(_get_report_type, string='Report Type')
    
    def to_print_sale(self, cr, uid, ids, context={}):
        this = self.browse(cr, uid, ids, context=context)
        ret=False
        if this.report_type=='sale_order_booking_report':
           report_name= 'sale_order_booking_report'    
           report_name1='Sale Order Booking Report'  
        elif this.report_type=='sale_order_analysis':
           report_name= 'sale_order_analysis'    
           report_name1='Sale Order Analysis Report'  
        elif this.report_type=='sale_price_variance':
           report_name= 'sale_price_variance'    
           report_name1='Sale Price Variance Report'  
        
        else:
            ret=super(kts_wms_sale_order_reports, self).to_print_sale(cr, uid, ids, context=context)
        
        if ret:
           return ret
        else:
           context.update({'this':this, 'uiModelAndReportModelSame':False})
           return do_print_setup(self,cr, uid, ids, {'name':report_name1, 'model':'kts.sale.reports','report_name':report_name},
                False,False,context)
    
    def sale_order_booking_report(self):
        lines=[]
        
        move_lines=self.env['sale.order'].search([('date_order','>=',self.date_start),('date_order','<=',self.date_stop),('state','=','sale')],order='date_order, partner_id, id asc')
        i=0
        customer=''
        so=''
        for line in move_lines:
            if line.partner_id.name!=customer: 
                  customer=line.partner_id.name
                  customer1=customer
            else:
                 customer1=''
            lines.append({
                          'customer':customer1,
                          'product':'',
                          'so':''  
                            }) 
            if line.name!=so:
                so=line.name
                so1=so
            else:
                so1=''
            lines.append({
                          'customer':'',
                          'product':'',
                          'so':so1  
                            }) 
            
            for so_line in line.order_line:
                i+=1
                lines.append({
                          'sr_no':i,
                          'customer':'',
                          'so':'',
                          'product':so_line.product_id.name,
                          'qty':so_line.product_uom_qty,
                          'shipment_date':line.date_order,
                          'remarks':line.note
                          })
        return lines
    def sale_order_analysis(self):
        lines=[]
        
        move_lines=self.env['sale.order'].search([('date_order','>=',self.date_start),('date_order','<=',self.date_stop),('state','=','sale')],order='date_order, partner_id asc')
        i=0
        name=''
        total=0.0
        for line in move_lines:
            i+=1
            total+=line.amount_untaxed
            lines.append({
                          'sr_no':i,
                          'name':line.name,
                          'amount':line.amount_untaxed,
                          'sale_man':line.user_id.name
                          })
      
        lines.append({
                      'sr_no':'',
                      'name':'Total',
                      'amount':total,
                      'sale_man':''
                      })
  
        return lines
    
    def sale_price_variance(self):
        lines=[]
        date_start=self.date_start
        date_stop=self.date_stop
        self.env.cr.execute('select '
                            'min(aa.price_unit), max(aa.price_unit), sum(aa.weighted_cost)/sum(aa.product_uom_qty), ' 
                            'aa.product_id, aa.name_template ' 
                            'from'
                            '(select '
                            'b.product_id, b.price_unit, b.product_uom_qty, b.product_uom_qty*b.price_unit as weighted_cost, c.name_template '
                            'from '
                            'sale_order a, sale_order_line b, product_product c '
                            'where '
                            'a.id=b.order_id and '
                            'date_order between %s and %s and b.product_id=c.id) aa '
                            'group by aa.product_id, aa.name_template',(date_start,date_stop))
        move_lines=self.env.cr.fetchall()
        i=0
        for line in move_lines:
            i+=1
            lines.append({
                          'sr_no':i,
                          'product_name':line[4],
                          'min':line[0],
                          'max':line[1],
                          'avg':line[2]
                          
                          }) 
        return lines  
    
    
class kts_wms_account_payment(models.Model):
    _inherit='account.payment'
    
    @api.multi
    def do_print_checks(self):
        this=self 
        report_name= 'cheque_print'    
        report_name1='Cheque'  
        context=self._context.copy()
        context.update({'this':this, 'uiModelAndReportModelSame':False})
        return do_print_setup(self.pool.get('account.payment'), self._cr, self._uid, self.ids, {'name':report_name1, 'model':'account.payment','report_name':report_name},
                False,False,context)


class kts_bin_account_reports(models.Model):
    _inherit='kts.account.report' 
    def get_move_lines(self):
         move_obj=[]
         ret=super(kts_bin_account_reports, self).get_move_lines()
         if self.report_type=='customer_ageing_report':
              move_obj = self.customer_ageing_report()
         elif self.report_type=='vendor_ageing_report':
              move_obj = self.vendor_ageing_report()
         
         elif ret:
             return ret
         return move_obj
    
    def _get_report_type(self):
        report_type=super(kts_bin_account_reports, self)._get_report_type()
        report_type.append(('customer_ageing_report','Customer Ageing Report'))
        report_type.append(('vendor_ageing_report','Vendor Ageing Report'))
        
        return report_type 
    
    report_type=fields.Selection(_get_report_type, string='Report Type')
    
    def to_print_account(self, cr, uid, ids, context={}):
           this = self.browse(cr, uid, ids, context=context) 
           ret=False
           if this.report_type=='customer_ageing_report':
              report_name= 'customer_ageing_report'    
              report_name1='Customer Ageing Report'  
           elif this.report_type=='vendor_ageing_report':
              report_name= 'vendor_ageing_report'    
              report_name1='Vendor Ageing Report'  
                  
           else:
            ret=super(kts_bin_account_reports, self).to_print_account(cr, uid, ids, context=context)
        
           if ret:
               return ret
           else:
               context.update({'this':this, 'uiModelAndReportModelSame':False})
               return do_print_setup(self,cr, uid, ids, {'name':report_name1, 'model':'kts.account.report','report_name':report_name},
                    False,False,context)
    
    def customer_ageing_report(self):
        lines=[]
        date_today=fields.Date.today()
        move_lines=self.env['account.invoice'].search([('type','=','out_invoice'),('state','=','open'),('date_due','<',date_today)],order='partner_id')
        i=0
        partner=''
        for line in move_lines:
            i+=1
            if line.partner_id.name!=partner:
                partner=line.partner_id.name
                partner1=partner
            else:
                partner1=''    
            
            lines.append({
                         'partner':partner1, 
                         'invoice':'', 
                          })
            
            days=(fields.Date.from_string(date_today)-fields.Date.from_string(line.date_due))
            lines.append({
                         'sr_no':i,
                         'partner':'', 
                         'invoice':line.number, 
                         'days':days,
                         'amount':line.residual,  
                          })
            
        return lines  
    
    def vendor_ageing_report(self):
        lines=[]
        date_today=fields.Date.today()
        move_lines=self.env['account.invoice'].search([('type','=','in_invoice'),('state','=','open'),('date_due','<',date_today)],order='partner_id')
        i=0
        partner=''
        for line in move_lines:
            i+=1
            if line.partner_id.name!=partner:
                partner=line.partner_id.name
                partner1=partner
            else:
                partner1=''    
            days=(fields.Date.from_string(date_today)-fields.Date.from_string(line.date_due))
            
            lines.append({
                         'partner':partner1, 
                         'invoice':'', 
                          })
            
            lines.append({
                         'sr_no':i,
                         'partner':'', 
                         'invoice':line.number, 
                         'days':days,
                         'amount':line.residual,  
                          })
            
        return lines  



class kts_report_action_xml_bin(models.Model):
      _inherit='ir.actions.report.xml'
      def get_report_keys(self, cr, uid, ids, context):
          report_keys=super(kts_report_action_xml_bin, self).get_report_keys(cr, uid, ids, context=context)
          report_keys.append({'name':'Putaway Receipt', 'report_sxw_content_data':'putaway_receipt','model':'kts.inventory.reports', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Stock Bin', 'report_sxw_content_data':'stock_bin','model':'kts.inventory.reports', 'deferred':'adaptive',},)                         
          report_keys.append({'name':'Stock Physical Verification', 'report_sxw_content_data':'stock_physical_verification','model':'kts.inventory.reports', 'deferred':'adaptive',},)                         
          report_keys.append({'name':'Product Warranty Report', 'report_sxw_content_data':'product_warranty_report','model':'kts.inventory.reports', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Picking List', 'report_sxw_content_data':'picking_list','model':'kts.inventory.reports', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Packing List', 'report_sxw_content_data':'packing_list','model':'kts.inventory.reports', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Shipping Label', 'report_sxw_content_data':'shipping_label','model':'stock.picking', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Vendor Lead Time', 'report_sxw_content_data':'vendor_lead_time','model':'kts.purchase.reports', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Sale Order Booking Report', 'report_sxw_content_data':'sale_order_booking_report','model':'kts.sale.reports', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Sale Order Analysis Report', 'report_sxw_content_data':'sale_order_analysis','model':'kts.sale.reports', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Sale Price Variance Report', 'report_sxw_content_data':'sale_price_variance','model':'kts.sale.reports', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Purchase Price Variance Report', 'report_sxw_content_data':'purchase_price_variance','model':'kts.purchase.reports', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Product Lead Time', 'report_sxw_content_data':'product_lead_time','model':'kts.purchase.reports', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Cheque', 'report_sxw_content_data':'cheque_print','model':'account.payment', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Product Pricelist Weigthed Cost', 'report_sxw_content_data':'product_pricelist_weigthed_cost','model':'kts.inventory.reports', 'deferred':'adaptive',},)                         
          report_keys.append({'name':'Procurement Order Summary', 'report_sxw_content_data':'procurement_order_summary','model':'kts.inventory.reports', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Bin Code', 'report_sxw_content_data':'bin_code','model':'kts.wms.bin', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Customer Ageing Report', 'report_sxw_content_data':'customer_ageing_report','model':'kts.account.report', 'deferred':'adaptive',},)                     
          report_keys.append({'name':'Vendor Ageing Report', 'report_sxw_content_data':'vendor_ageing_report','model':'kts.account.report', 'deferred':'adaptive',},)                     
                   
          return report_keys   
      
      
      


               
        