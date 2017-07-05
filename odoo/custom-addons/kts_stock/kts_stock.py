from openerp import models 
from openerp.tools.translate import _
from openerp.osv import fields, osv
from lxml import etree
from openerp.tools.float_utils import float_compare, float_round
import time
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from openerp.exceptions import UserError, AccessError
class kts_stock_for_picking(models.Model):
    _inherit='stock.picking'

    def _state_get(self, cr, uid, ids, field_name, arg, context=None):
        ret=super(kts_stock_for_picking, self)._state_get(cr, uid, ids, field_name, arg,context=context)
        for key, value in ret.iteritems():
           picking_obj=self.browse(cr, uid, key, context=context)
           if value=='done' and picking_obj.picking_type_id.code=='incoming' and picking_obj:
              
              self.write(cr, uid, key,{'grn_no':self.pool.get('ir.sequence').next_by_code(cr, uid, 'kts.grn.no')}, context=context) 
        
        return ret
    
    def _get_pickings(self, cr, uid, ids, context=None):
        res = set()
        for move in self.browse(cr, uid, ids, context=context):
            if move.picking_id:
                res.add(move.picking_id.id)
        return list(res) 
    
    _columns = { 
     'location_id': fields.many2one('stock.location', required=True, string="Source Location Zone",
                                       states={'draft': [('readonly', True)],'partially_available':[('readonly', True)],'confirmed':[('readonly', True)],'assigned':[('readonly', True)]}),
     'location_dest_id': fields.many2one('stock.location', required=True,string="Destination Location Zone",
                                            readonly=True, states={'draft': [('readonly', True)]}),
     'grn_no':fields.char(string='GRN NO',readonly=True),
     'transporter_name':fields.char(string='Transporter Name'),
     'chalan_no':fields.char(string='Chalan No'),
     'state': fields.function(_state_get, type="selection", copy=False,
            store={
                'stock.picking': (lambda self, cr, uid, ids, ctx: ids, ['move_type', 'launch_pack_operations'], 20),
                'stock.move': (_get_pickings, ['state', 'picking_id', 'partially_available'], 20)},
            selection=[
                ('draft', 'Draft'),
                ('cancel', 'Cancelled'),
                ('waiting', 'Waiting Another Operation'),
                ('confirmed', 'Waiting Availability'),
                ('partially_available', 'Partially Available'),
                ('assigned', 'Available'),
                ('done', 'Done'),
                ], string='Status', readonly=True, select=True, track_visibility='onchange',
            help="""
                * Draft: not confirmed yet and will not be scheduled until confirmed\n
                * Waiting Another Operation: waiting for another move to proceed before it becomes automatically available (e.g. in Make-To-Order flows)\n
                * Waiting Availability: still waiting for the availability of products\n
                * Partially Available: some products are available and reserved\n
                * Ready to Transfer: products reserved, simply waiting for confirmation.\n
                * Transferred: has been processed, can't be modified or cancelled anymore\n
                * Cancelled: has been cancelled, can't be confirmed anymore"""
        ),
           }
    _defaults = {
        'transporter_name':'',
        'chalan_no':''
      }
    
    def recompute_remaining_qty(self, cr, uid, picking, done_qtys=False, context=None):
        def _create_link_for_index(operation_id, index, product_id, qty_to_assign, quant_id=False):
            move_dict = prod2move_ids[product_id][index]
            qty_on_link = min(move_dict['remaining_qty'], qty_to_assign)
            self.pool.get('stock.move.operation.link').create(cr, uid, {'move_id': move_dict['move'].id, 'operation_id': operation_id, 'qty': qty_on_link, 'reserved_quant_id': quant_id}, context=context)
            if move_dict['remaining_qty'] == qty_on_link:
                #prod2move_ids[product_id].pop(index)
                pass
            else:
                move_dict['remaining_qty'] -= qty_on_link
            return qty_on_link

        def _create_link_for_quant(operation_id, quant, qty):
            """create a link for given operation and reserved move of given quant, for the max quantity possible, and returns this quantity"""
            if not quant.reservation_id.id:
                return _create_link_for_product(operation_id, quant.product_id.id, qty)
            qty_on_link = 0
            for i in range(0, len(prod2move_ids[quant.product_id.id])):
                if prod2move_ids[quant.product_id.id][i]['move'].id != quant.reservation_id.id:
                    continue
                qty_on_link = _create_link_for_index(operation_id, i, quant.product_id.id, qty, quant_id=quant.id)
                break
            return qty_on_link

        def _create_link_for_product(operation_id, product_id, qty):
            '''method that creates the link between a given operation and move(s) of given product, for the given quantity.
            Returns True if it was possible to create links for the requested quantity (False if there was not enough quantity on stock moves)'''
            qty_to_assign = qty
            prod_obj = self.pool.get("product.product")
            product = prod_obj.browse(cr, uid, product_id)
            rounding = product.uom_id.rounding
            qtyassign_cmp = float_compare(qty_to_assign, 0.0, precision_rounding=rounding)
            if prod2move_ids.get(product_id):
                while prod2move_ids[product_id] and qtyassign_cmp > 0:
                    qty_on_link = _create_link_for_index(operation_id, 0, product_id, qty_to_assign, quant_id=False)
                    qty_to_assign -= qty_on_link
                    qtyassign_cmp = float_compare(qty_to_assign, 0.0, precision_rounding=rounding)
            return qtyassign_cmp == 0

        uom_obj = self.pool.get('product.uom')
        package_obj = self.pool.get('stock.quant.package')
        quant_obj = self.pool.get('stock.quant')
        link_obj = self.pool.get('stock.move.operation.link')
        quants_in_package_done = set()
        prod2move_ids = {}
        still_to_do = []
        #make a dictionary giving for each product, the moves and related quantity that can be used in operation links
        for move in [x for x in picking.move_lines if x.state not in ('done', 'cancel')]:
            if not prod2move_ids.get(move.product_id.id):
                prod2move_ids[move.product_id.id] = [{'move': move, 'remaining_qty': move.product_qty}]
            else:
                prod2move_ids[move.product_id.id].append({'move': move, 'remaining_qty': move.product_qty})

        need_rereserve = False
        #sort the operations in order to give higher priority to those with a package, then a serial number
        operations = picking.pack_operation_ids
        operations = sorted(operations, key=lambda x: ((x.package_id and not x.product_id) and -4 or 0) + (x.package_id and -2 or 0) + (x.pack_lot_ids and -1 or 0))
        #delete existing operations to start again from scratch
        links = link_obj.search(cr, uid, [('operation_id', 'in', [x.id for x in operations])], context=context)
        if links:
            link_obj.unlink(cr, uid, links, context=context)
        #1) first, try to create links when quants can be identified without any doubt
        for ops in operations:
            lot_qty = {}
            for packlot in ops.pack_lot_ids:
                lot_qty[packlot.lot_id.id] = uom_obj._compute_qty(cr, uid, ops.product_uom_id.id, packlot.qty, ops.product_id.uom_id.id)
            #for each operation, create the links with the stock move by seeking on the matching reserved quants,
            #and deffer the operation if there is some ambiguity on the move to select
            if ops.package_id and not ops.product_id and (not done_qtys or ops.qty_done):
                #entire package
                quant_ids = package_obj.get_content(cr, uid, [ops.package_id.id], context=context)
                for quant in quant_obj.browse(cr, uid, quant_ids, context=context):
                    remaining_qty_on_quant = quant.qty
                    if quant.reservation_id:
                        #avoid quants being counted twice
                        quants_in_package_done.add(quant.id)
                        qty_on_link = _create_link_for_quant(ops.id, quant, quant.qty)
                        remaining_qty_on_quant -= qty_on_link
                    if remaining_qty_on_quant:
                        still_to_do.append((ops, quant.product_id.id, remaining_qty_on_quant))
                        need_rereserve = True
            elif ops.product_id.id:
                #Check moves with same product
                product_qty = ops.qty_done if done_qtys else ops.product_qty
                qty_to_assign = uom_obj._compute_qty_obj(cr, uid, ops.product_uom_id, product_qty, ops.product_id.uom_id, context=context)
                for move_dict in prod2move_ids.get(ops.product_id.id, []):
                    move = move_dict['move']
                    for quant in move.reserved_quant_ids:
                        if not qty_to_assign > 0:
                            break
                        if quant.id in quants_in_package_done:
                            continue

                        #check if the quant is matching the operation details
                        if ops.package_id:
                            flag = quant.package_id and bool(package_obj.search(cr, uid, [('id', 'child_of', [ops.package_id.id])], context=context)) or False
                        else:
                            flag = not quant.package_id.id
                        flag = flag and (ops.owner_id.id == quant.owner_id.id)
                        if flag:
                            if not lot_qty:
                                max_qty_on_link = min(quant.qty, qty_to_assign)
                                qty_on_link = _create_link_for_quant(ops.id, quant, max_qty_on_link)
                                qty_to_assign -= qty_on_link
                            else:
                                if lot_qty.get(quant.lot_id.id): #if there is still some qty left
                                    max_qty_on_link = min(quant.qty, qty_to_assign, lot_qty[quant.lot_id.id])
                                    qty_on_link = _create_link_for_quant(ops.id, quant, max_qty_on_link)
                                    qty_to_assign -= qty_on_link
                                    lot_qty[quant.lot_id.id] -= qty_on_link

                qty_assign_cmp = float_compare(qty_to_assign, 0, precision_rounding=ops.product_id.uom_id.rounding)
                if qty_assign_cmp > 0:
                    #qty reserved is less than qty put in operations. We need to create a link but it's deferred after we processed
                    #all the quants (because they leave no choice on their related move and needs to be processed with higher priority)
                    still_to_do += [(ops, ops.product_id.id, qty_to_assign)]
                    need_rereserve = True

        #2) then, process the remaining part
        all_op_processed = True
        for ops, product_id, remaining_qty in still_to_do:
            all_op_processed = _create_link_for_product(ops.id, product_id, remaining_qty) and all_op_processed
        return (need_rereserve, all_op_processed)
        
    def _create_backorder(self, cr, uid, picking, backorder_moves=[], context=None):
        if not backorder_moves:
            backorder_moves = picking.move_lines
        backorder_move_ids = [x.id for x in backorder_moves if x.state not in ('done', 'cancel')]
        if 'do_only_split' in context and context['do_only_split']:
            backorder_move_ids = [x.id for x in backorder_moves if x.id not in context.get('split', [])]

        if backorder_move_ids:
            backorder_id = self.copy(cr, uid, picking.id, {
                'name': '/',
                'move_lines': [],
                'pack_operation_ids': [],
                'backorder_id': picking.id,
                'transporter_name':'',
                'chalan_no':''
            })
            backorder = self.browse(cr, uid, backorder_id, context=context)
            self.message_post(cr, uid, picking.id, body=_("Back order <em>%s</em> <b>created</b>.") % (backorder.name), context=context)
            move_obj = self.pool.get("stock.move")
            move_obj.write(cr, uid, backorder_move_ids, {'picking_id': backorder_id}, context=context)

            if not picking.date_done:
                self.write(cr, uid, [picking.id], {'date_done': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)}, context=context)
            self.action_confirm(cr, uid, [backorder_id], context=context)
            self.action_assign(cr, uid, [backorder_id], context=context)
            return backorder_id
        return False

class kts_stock_move_scrap(osv.osv):
    _inherit = "stock.move"
    
    def action_scrap(self, cr, uid, ids, quantity, location_id, restrict_lot_id=False, restrict_partner_id=False, context=None):
        stock_picking_obj = self.pool.get('stock.picking')
        stock_move_obj=self.pool.get('stock.move')
        if context.get('active_id'):
            move = self.pool.get('stock.move').browse(cr, uid, context['active_id'], context=context)
        if not move.picking_id:
               if move.partial_job_card_qty < quantity:
                  raise UserError(_('You can not scrap more than reserve qty'))
               stock_move_obj.do_unreserve(cr, uid, ids, context=context)
               res=super(kts_stock_move_scrap, self).action_scrap(cr, uid, ids, quantity, location_id, restrict_lot_id, restrict_partner_id, context=context)
               stock_move_obj.action_assign(cr, uid, ids, context=context)              
               res1=res.pop()
               stock_move_obj.write(cr, uid, res1, {'partial_job_card_qty': quantity}, context=context)
               stock_move_obj.write(cr, uid, ids, {'partial_job_card_qty': move.partial_job_card_qty-quantity}, context=context)
        else: 
            pick=move.picking_id
            stock_picking_obj.do_unreserve(cr, uid, pick.id, context=context)
            res=super(kts_stock_move_scrap, self).action_scrap(cr, uid, ids, quantity, location_id, restrict_lot_id, restrict_partner_id, context=context)
            stock_picking_obj.action_assign(cr, uid, pick.id, context=context)              
               
            res1=res.pop()
            new_move=self.pool.get('stock.move').browse(cr, uid,res1, context=context)
            if move.picking_id.picking_type_id.code=='internal': 
                  if move.product_qty - new_move.product_qty > 0.0:
                      self.pool.get('stock.move').write(cr, uid, [move.id], {
                           'product_uom_qty': move.product_uom_qty - new_move.product_uom_qty, 
                             }, context=context)
                  else:
                      self.pool.get('stock.move').write(cr, uid, [move.id], {'state': 'cancel'}, context=context)                 
               
                   
                  stock_picking_obj.do_unreserve(cr, uid, [pick.id], context=context) 
                  stock_picking_obj.action_assign(cr, uid, [pick.id], context=context)
               #stock_picking_obj.do_prepare_partial(cr, uid, [pick.id], context=context)                        
        return True


class kts_scrap_wizard(osv.osv_memory):
        
    _inherit="stock.move.scrap"
    def default_get(self, cr, uid, fields, context=None):
        res=super(kts_scrap_wizard, self).default_get(cr, uid, fields, context=context) 
        move = self.pool.get('stock.move').browse(cr, uid, context['active_id'], context=context)
        if res['product_id']:
            product_id=res['product_id']
        product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
        if product.tracking=='serial' or product.tracking=='lot':    
            if move.picking_id.picking_type_id.code=='incoming':
               lot_id=self.pool.get('stock.production.lot').create(cr,uid,{
                                                                'name':self.pool.get('ir.sequence').next_by_code(cr, uid, 'kts.serial.no', context=context),
                                                                'product_id':product_id,
                                                                },context=context)
               res.update({'restrict_lot_id':lot_id})
           
                
        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):            
       
         res = super(kts_scrap_wizard, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
         move = self.pool.get('stock.move').browse(cr, uid, context['active_id'], context=context)
         product_id=context.get('default_product_id')
         picking_id=move.picking_id 
         line=[]
         lot_ids=[]
         final_lot_ids=[]
         stock_quant_obj=self.pool.get('stock.quant')
         
         stock_quants=stock_quant_obj.search(cr,uid,[('reservation_id','=',move.id)],context=context)
         stock_quant_lines=stock_quant_obj.browse(cr, uid, stock_quants, context=context)
            
         if len(stock_quants)>0:
            for line2 in stock_quant_lines:
                   final_lot_ids.append(line2.lot_id.id) 
                   
         doc = etree.XML(res['arch'])
         nodes = doc.xpath("//field[@name='restrict_lot_id']")
         if len(stock_quants)>0:
            domain = '[("id", "in", '+ str(final_lot_ids)+'),("product_id","=",product_id)]'
         else:
             domain='[("product_id","=",product_id)]'
         for node in nodes:
                node.set('domain', domain)
                node.set('no_create', "True")
                node.set('no_create_edit', "True")
                node.set('no_quick_create', "True")
               
         res['arch'] = etree.tostring(doc)
         return res 


    def onchange_product_qty(self, cr, uid, ids,product_id, product_qty, context=None):
        if product_qty>1.0:
            res={}
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            if product.tracking=='serial':
                res.update({'product_qty':0.0})
                return{'value':res,
                       'warning':{'title':'UserError', 'message':'Product is serial Tracker please select 1 qty!'}   
                       }
    
    def move_scrap(self, cr, uid, ids, context=None):
        """ To move scrapped products
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID or list of IDs if we want more than one
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        move_ids = context['active_ids']
        for data in self.browse(cr, uid, ids):
            move_obj.action_scrap(cr, uid, move_ids,
                             data.product_qty, data.location_id.id, restrict_lot_id=data.restrict_lot_id.id,
                             context=context)
        
        if context.get('active_id'):
            move = self.pool.get('stock.move').browse(cr, uid, context['active_id'], context=context)    
            if move.picking_id:
                return {
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'stock.picking',
                    'type': 'ir.actions.act_window',
                    'res_id': move.picking_id.id,
                    'context': context
                }
        return {'type': 'ir.actions.act_window_close'}
      