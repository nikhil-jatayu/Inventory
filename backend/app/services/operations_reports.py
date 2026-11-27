"""One report payload for preview, Excel and PDF. Quantities, not currency."""
from datetime import date, datetime, timezone
from decimal import Decimal
from collections import defaultdict
from sqlalchemy import select, func
from app.models import (Item, Unit, Dispatch, DispatchPlan, SalesRecord, Rejection,
    Purchase, PurchaseLine, PurchasePlan, PurchaseRejection, StockTransaction)
from app.services.balances import rejected_for_dispatch, purchase_balances
from app.core.errors import AppError

REPORTS = {
    'management': 'Management Summary', 'stock': 'Stock vs Dispatch Plan',
    'dispatch': 'Dispatch Performance', 'sales': 'Sales Reconciliation',
    'purchase': 'Purchase Plan vs Actual Purchase', 'unit-rejections': 'Unit Rejections',
    'purchase-rejections': 'Purchase Rejections', 'ledger': 'Inventory Stock Ledger',
}
ZERO = Decimal(0)

def build_report(db, *, kind, date_from, date_to, project=None, family=None, item_id=None, unit_id=None):
    if kind not in REPORTS: raise AppError(422, 'Unknown report type')
    if not 0 <= (date_to-date_from).days <= 366: raise AppError(422, 'Choose an ordered period of at most 367 days')
    if unit_id and kind in {'purchase','purchase-rejections','ledger','stock','management'}:
        raise AppError(422, 'This report uses shared inventory or purchases; select all units')
    filters = []
    if project: filters.append(Item.project == project)
    if family: filters.append(Item.family == family)
    if item_id: filters.append(Item.id == item_id)
    items = {i.id:i for i in db.scalars(select(Item).where(*filters).order_by(Item.name,Item.project)).all()}
    ids = list(items)
    units = {u.id:u.name for u in db.scalars(select(Unit)).all()}
    if unit_id and unit_id not in units: raise AppError(422,'Unknown unit')
    def name(i): return items[i].name
    def proj(i): return items[i].project
    def unit(i): return units.get(i,'Unassigned')
    def records(model, column, unit_col=None):
        q = select(model).where(model.item_id.in_(ids),column>=date_from,column<=date_to)
        if unit_id and unit_col is not None: q=q.where(unit_col==unit_id)
        return db.scalars(q.order_by(column,model.id)).all()
    def section(title, columns, rows): return {'title':title,'columns':columns,'rows':rows}
    sections=[]; metrics=[]
    def metric(label,value): metrics.append({'label':label,'value':value})
    notes=['All quantities are pieces. No prices or tax values are recorded.',
           'Plan totals are allocated by plan start date; actual activity is allocated by transaction date.',
           'Net sales are restated in the original invoice month using all linked rejections recorded to date.',
           'Historical unlinked rejections and purchases are preserved but cannot be applied to individual balances.']
    plans=records(DispatchPlan,DispatchPlan.planned_date,DispatchPlan.unit_id) if kind in {'management','stock','dispatch'} else []
    gross=records(Dispatch,Dispatch.dispatch_date,Dispatch.unit_id) if kind in {'management','dispatch'} else []
    if kind in {'management','dispatch'}:
        metric('Dispatch plan',sum((r.quantity for r in plans),ZERO)); metric('Actual dispatch in period',sum((r.quantity for r in gross),ZERO))
        metric('Outstanding on selected plans',sum((r.quantity-r.fulfilled_quantity for r in plans),ZERO))
        sections.append(section('Dispatch plans',['Plan','Item','Project','Unit','Start','End','Planned','Fulfilled to date','Outstanding'],[[p.id,name(p.item_id),proj(p.item_id),unit(p.unit_id),p.planned_date,p.planned_end_date,p.quantity,p.fulfilled_quantity,p.quantity-p.fulfilled_quantity] for p in plans]))
        sections.append(section('Actual dispatches',['Dispatch','Plan','Item','Project','Unit','Date','Quantity'],[[d.id,d.plan_id,name(d.item_id),proj(d.item_id),unit(d.unit_id),d.dispatch_date,d.quantity] for d in gross]))
    if kind in {'management','stock'}:
        stock=dict(db.execute(select(StockTransaction.item_id,func.sum(StockTransaction.quantity)).where(StockTransaction.item_id.in_(ids)).group_by(StockTransaction.item_id)).all())
        pending=defaultdict(lambda:ZERO)
        for p in plans: pending[p.item_id]+=p.quantity-p.fulfilled_quantity
        active=[i for i in items.values() if i.is_active]
        # Shared stock, active items only, identical to dashboard coverage semantics.
        rows=[[i.name,i.project,i.family,stock.get(i.id,ZERO),pending[i.id],max(ZERO,pending[i.id]-stock.get(i.id,ZERO))] for i in active]
        metric('Live available stock',sum((r[3] for r in rows),ZERO)); metric('Item-level shortfall',sum((r[5] for r in rows),ZERO))
        notes.append('Stock coverage is live shared stock for active items, not historical month-end or unit-level stock.')
        sections.append(section('Live stock vs outstanding dispatch',['Item','Project','Family','Available now','Outstanding','Shortfall'],rows))
    if kind in {'management','sales','dispatch'}:
        q=select(SalesRecord,rejected_for_dispatch(SalesRecord.dispatch_id)).where(SalesRecord.item_id.in_(ids),SalesRecord.invoice_date>=date_from,SalesRecord.invoice_date<=date_to)
        if unit_id: q=q.where(SalesRecord.unit_id==unit_id)
        sales=db.execute(q.order_by(SalesRecord.invoice_date,SalesRecord.id)).all()
        metric('Gross sales',sum((s.quantity for s,r in sales),ZERO)); metric('Linked rejected quantity',sum((r for s,r in sales),ZERO)); metric('Net sales',sum((s.quantity-r for s,r in sales),ZERO))
        sections.append(section('Sales reconciliation',['Invoice','Dispatch','Date','Item','Project','Unit','PO','Gross','Rejected','Net'],[[s.invoice_number,s.dispatch_id,s.invoice_date,name(s.item_id),proj(s.item_id),unit(s.unit_id),s.po_number,s.quantity,r,s.quantity-r] for s,r in sales]))
    if kind in {'management','purchase'}:
        pp=records(PurchasePlan,PurchasePlan.planned_date)
        rows=[]
        for p in pp:
            received,cancelled,outstanding=purchase_balances(db,p)
            rows.append([p.id,name(p.item_id),proj(p.item_id),p.planned_date,p.planned_end_date,p.quantity,received,cancelled,outstanding])
        for idx,label in [(5,'Purchase planned'),(6,'Received on selected plans'),(7,'Cancelled on selected plans'),(8,'Outstanding purchase')]: metric(label,sum((r[idx] for r in rows),ZERO))
        sections.append(section('Purchase plan balances',['Plan','Item','Project','Start','End','Planned','Received to date','Cancelled to date','Outstanding'],rows))
        receipts=db.execute(select(PurchaseLine,Purchase).join(Purchase,Purchase.id==PurchaseLine.purchase_id).where(PurchaseLine.item_id.in_(ids),Purchase.purchase_date>=date_from,Purchase.purchase_date<=date_to).order_by(Purchase.purchase_date,PurchaseLine.id)).all()
        metric('Receipts in period',sum((l.quantity for l,p in receipts),ZERO));metric('Unallocated receipts in period',sum((l.quantity for l,p in receipts if l.plan_id is None),ZERO))
        sections.append(section('Purchase receipts',['Receipt','Date','Plan','Item','Project','Quantity','Link status'],[[f'PURCHASE-{p.id}',p.purchase_date,l.plan_id,name(l.item_id),proj(l.item_id),l.quantity,'Linked' if l.plan_id else 'Legacy unlinked'] for l,p in receipts]))
    if kind in {'management','unit-rejections','sales'}:
        rej=records(Rejection,Rejection.rejection_date,Rejection.unit_id)
        metric('Unit rejections recorded in period',sum((r.quantity for r in rej),ZERO));metric('Unallocated unit rejections in period',sum((r.quantity for r in rej if r.dispatch_id is None),ZERO))
        sections.append(section('Unit rejection register',['RGP','Date','Unit','Item','Project','Dispatch','Quantity','Link status'],[[r.rgp_number,r.rejection_date,unit(r.unit_id),name(r.item_id),proj(r.item_id),r.dispatch_id,r.quantity,'Linked' if r.dispatch_id else 'Legacy unlinked'] for r in rej]))
        totals=defaultdict(lambda:ZERO)
        for r in rej: totals[unit(r.unit_id)]+=r.quantity
        sections.append(section('Rejections by unit',['Unit','Rejected quantity'],[[u,q] for u,q in sorted(totals.items())]))
    if kind in {'management','purchase-rejections','purchase'}:
        pr=records(PurchaseRejection,PurchaseRejection.rejection_date)
        metric('Purchase rejections recorded in period',sum((r.quantity for r in pr),ZERO));metric('Unallocated purchase rejections in period',sum((r.quantity for r in pr if r.plan_id is None),ZERO))
        sections.append(section('Purchase rejection register',['RGP','Date','Item','Project','Plan','Quantity','Link status'],[[r.rgp_number,r.rejection_date,name(r.item_id),proj(r.item_id),r.plan_id,r.quantity,'Linked' if r.plan_id else 'Legacy unlinked'] for r in pr]))
    if kind=='ledger':
        tx=records(StockTransaction,StockTransaction.date)
        opening=dict(db.execute(select(StockTransaction.item_id,func.sum(StockTransaction.quantity)).where(StockTransaction.item_id.in_(ids),StockTransaction.date<date_from).group_by(StockTransaction.item_id)).all())
        movements=defaultdict(lambda:ZERO)
        for t in tx:movements[t.item_id]+=t.quantity
        sections.append(section('Stock balances',['Item','Project','Opening','Net movement','Closing'],[[i.name,i.project,opening.get(i.id,ZERO),movements[i.id],opening.get(i.id,ZERO)+movements[i.id]] for i in items.values()]))
        sections.append(section('Stock ledger',['Date','Item','Project','Type','Signed quantity','Reference','Remarks'],[[t.date,name(t.item_id),proj(t.item_id),t.type.value,t.quantity,t.ref,t.remarks] for t in tx]))
    return {'title':REPORTS[kind],'kind':kind,'date_from':date_from,'date_to':date_to,
            'generated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'filters':{'Project':project or 'All','Family':family or 'All','Item':f'{name(item_id)} / {proj(item_id)}' if item_id in items else ('All' if not item_id else f'#{item_id}'),'Unit':unit(unit_id) if unit_id else 'All'},
            'metrics':metrics,'sections':sections,'notes':notes}
