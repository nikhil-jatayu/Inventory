"""Local Inventory demonstration utility. Never run against a production database."""
import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.base import Base, Item, Unit, User, StockTransaction
from app.seed import CLIENT_ITEMS
from app.schemas.dispatches import DispatchCreate
from app.schemas.planning import DispatchPlanCreate
from app.schemas.purchase_orders import PurchaseOrderCreate
from app.schemas.purchases import PurchaseCreate, PurchasePlanCreate, PurchaseRejectionBatchCreate
from app.schemas.rejections import RejectionBatchCreate
from app.services.dispatches import record_dispatch
from app.services.planning import create_dispatch_plan
from app.services.purchase_orders import create_purchase_order
from app.services.purchases import create_purchase, create_purchase_plan, create_purchase_rejection_batch
from app.services.rejections import record_rejection_batch

STATE = Path(__file__).resolve().parents[2] / '.inventory-demo-state.json'
TABLES = list(Base.metadata.sorted_tables)
MASTER = {'items', 'units', 'users'}

LEGACY_ADDITIONS = {"rejections": {"dispatch_id", "batch_id"}, "purchase_lines": {"plan_id"}, "purchase_rejections": {"plan_id", "batch_id"}}

def snapshot(db, *, legacy=False):
    result = {}
    for table in TABLES:
        rows = db.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()
        values = [dict(r) for r in rows]
        if legacy:
            extra = LEGACY_ADDITIONS.get(table.name, set())
            if any(row[k] is not None for row in values for k in extra):
                raise RuntimeError("Linked transactions exist; old demo manifest cannot authorize deletion.")
            values = [{k:v for k,v in row.items() if k not in extra} for row in values]
        result[table.name] = {'count': len(rows), 'hash': hashlib.sha256(json.dumps(values, default=str, sort_keys=True).encode()).hexdigest(), 'keys': [[r[c.name] for c in table.primary_key.columns] for r in rows]}
    return result

def populate(db):
    items = {(i.name, i.project): i for i in db.scalars(select(Item)).all()}
    expected = [(i['name'], i['project']) for i in CLIENT_ITEMS]
    if set(items) != set(expected) or any(not items[k].is_active for k in expected):
        raise RuntimeError('Expected exactly the ten active client items.')
    ids = [items[k].id for k in expected]
    units = {u.name: u.id for u in db.scalars(select(Unit).where(Unit.is_active.is_(True))).all()}
    us = [units[f'Unit-{i}'] for i in range(1,5)]
    admin = db.scalar(select(User).where(User.username == 'admin', User.is_active.is_(True)))
    if admin is None: raise RuntimeError('Active admin required')
    today = date.today()
    current = today.replace(day=1)
    previous = (current-timedelta(days=1)).replace(day=1)
    following = (current+timedelta(days=32)).replace(day=1)
    def lines(indices, quantities): return [{'item_id':ids[i], 'quantity':q} for i,q in zip(indices,quantities)]
    # Receipts precede actual dispatches, and every receipt/cancellation has a plan.
    for j in range(18):
        a = j % 10; b = (j+3)%10
        d = previous + timedelta(days=j)
        receipt_lines=[]
        for item_index, qty in ((a,160+20*(j%4)),(b,120+15*(j%3))):
            plan=create_purchase_plan(db, PurchasePlanCreate(item_id=ids[item_index], quantity=qty+20, planned_date=d, planned_end_date=d+timedelta(days=4), remarks='DEMO receipt plan'),recorded_by=admin)
            receipt_lines.append({'item_id':ids[item_index], 'plan_id':plan.id, 'quantity':qty})
        create_purchase(db,PurchaseCreate(purchase_date=d,lines=receipt_lines),recorded_by=admin)
        if j < 3:
            create_purchase_rejection_batch(db,PurchaseRejectionBatchCreate(rgp_number=f'DEMO-PR/{j+1:03}',rejection_date=d,lines=[dict(line,quantity=10) for line in receipt_lines]),recorded_by=admin)
    for j in range(12):
        create_purchase_order(db, PurchaseOrderCreate(po_number=f'{910000+j:08d}', po_date=previous+timedelta(days=j), unit_ids=[us[j%4]], lines=lines([j%10,(j+1)%10],[180,240])))
    for j in range(15):
        d = today+timedelta(days=(j-3)*2)
        create_purchase_plan(db, PurchasePlanCreate(item_id=ids[j%10],quantity=100+20*j,planned_date=d,planned_end_date=d+timedelta(days=4+j%5),remarks='DEMO purchase schedule'),recorded_by=admin)
    delivered=[]
    for j in range(30):
        i=j%10; unit=us[j%4]
        if j<10:
            start=previous+timedelta(days=2+j); end=start+timedelta(days=8+j%5); qty=80+10*(j%4); parts=[qty//2,qty-qty//2]
        elif j<20:
            start=min(current+timedelta(days=2+(j-10)*2),today); end=start+timedelta(days=5+j%9); qty=90+10*(j%5); parts=([qty//2,qty-qty//2] if j%3==0 else [qty//3] if j%3==1 else [])
        else:
            start=following+timedelta(days=(j-20)*2); end=start+timedelta(days=6+j%7); qty=180+20*(j%5); parts=[]
        # A cross-month plan and a deliberate current-month shortage.
        if j==19: start=today; end=following+timedelta(days=5); qty=1500; parts=[]
        plan=create_dispatch_plan(db,DispatchPlanCreate(item_id=ids[i],unit_id=unit,planned_date=start,planned_end_date=end,quantity=qty))
        for k,q in enumerate(parts):
            result=record_dispatch(db,DispatchCreate(plan_id=plan.id,unit_id=unit,dispatch_date=min(today,start+timedelta(days=2+k*3)),quantity=q,po_number=f'{910000+j%12:08d}' if j%2==0 else None,remarks='DEMO dispatch'))
            delivered.append((result, unit, ids[i], q, min(today,start+timedelta(days=2+k*3))))
    for j, unit in enumerate(us):
        candidates=[(row,item,qty,d) for row,u,item,qty,d in delivered if u==unit][:2]
        if candidates:
            record_rejection_batch(db,RejectionBatchCreate(rgp_number=f'DEMO-RGP/{j+1:03}',unit_id=unit,rejection_date=min(today,max(d for _,_,_,d in candidates)+timedelta(days=1)),lines=[{'dispatch_id':row.id,'item_id':item,'quantity':min(qty,3+j)} for row,item,qty,d in candidates]),recorded_by=admin)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['seed','status','clear'])
    args=parser.parse_args()
    if engine.url.host not in {'localhost','127.0.0.1'} or engine.url.port!=5437 or engine.url.database!='inventory':
        raise SystemExit('Refusing: expected local inventory database on port 5437.')
    with engine.connect() as conn:
        with conn.begin():
            # Service commits release savepoints, not the enclosing transaction.
            conn.execute(text('LOCK TABLE '+', '.join(t.name for t in TABLES)+' IN SHARE ROW EXCLUSIVE MODE'))
            with Session(bind=conn,join_transaction_mode='create_savepoint',autoflush=False,expire_on_commit=False) as db:
                state=json.loads(STATE.read_text()) if STATE.exists() else None
                legacy = bool(state and not state.get("schema_version"))
                before=snapshot(db, legacy=legacy)
                if args.action=='status':
                    for name,v in before.items(): print(f'{name}: {v["count"]}')
                    print('Demo state:', 'unchanged' if state and before==state['after'] else 'changed or absent')
                    return
                if args.action=='seed':
                    if state: raise RuntimeError('Demo state already exists; use status.')
                    for name,v in before.items():
                        if name not in MASTER|{'stock_transactions','rejection_issues'} and v['count']:
                            raise RuntimeError(f'Existing transactions in {name}; refusing to seed.')
                    ledger=db.scalars(select(StockTransaction)).all()
                    if len(ledger)!=1 or ledger[0].ref!='CLIENT-ITEM-MASTER' or ledger[0].quantity!=1000:
                        raise RuntimeError('Unexpected opening stock; refusing to seed.')
                    populate(db)
                    db.flush()
                    after=snapshot(db)
                    if any(before[n]!=after[n] for n in MASTER): raise RuntimeError('Master data changed')
                    # Existing issue records must not be modified by batch service.
                    if before['rejection_issues']['count'] and before['rejection_issues']!=after['rejection_issues']:
                        raise RuntimeError('Existing rejection issue data would change.')
                    db.commit()
                    with STATE.open('x',encoding='utf-8') as f: json.dump({'schema_version':2,'before':before,'after':after},f,indent=2)
                    print('Demo records prepared:')
                    for n in after: print(f'{n}: +{after[n]["count"]-before[n]["count"]}')
                else:
                    if not state or before!=state['after']: raise RuntimeError('Database differs from recorded demo state; no deletion performed.')
                    if input('Type CLEAR DEMO to remove the recorded sample data: ')!='CLEAR DEMO': raise RuntimeError('Cancelled')
                    for table in reversed(TABLES):
                        old={tuple(k) for k in state['before'][table.name]['keys']}
                        for key in before[table.name]['keys']:
                            if tuple(key) not in old:
                                db.execute(table.delete().where(*[c==v for c,v in zip(table.primary_key.columns,key)]))
                    if snapshot(db, legacy=legacy)!=state['before']: raise RuntimeError('Baseline verification failed; rolling back.')
                    db.commit()
        if args.action=='clear': STATE.unlink()
    print('Completed:',args.action)

if __name__=='__main__': main()
