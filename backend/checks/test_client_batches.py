"""Isolated database regression tests; never touch the configured application DB."""
import unittest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from app.core.errors import AppError
from app.models.base import Base, Item, Unit, User, Role, Dispatch, DispatchPlan, SalesRecord, StockTransaction, StockTxnType, PurchasePlan
from app.schemas.dispatches import DispatchBatchCreate, DispatchCreate
from app.schemas.planning import DispatchPlanCreateBatch
from app.schemas.purchases import PurchasePlanCreateBatch, PurchaseCreate, PurchaseRejectionBatchCreate
from app.schemas.rejections import RejectionBatchCreate
from app.schemas.purchase_orders import PurchaseOrderCreate
from app.services import dispatches, planning, purchases, rejections, purchase_orders

class BatchTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
        self.today = date.today()
        self.user = User(username='test',full_name='Test',hashed_password='not-a-real-password',role=Role.ADMIN)
        self.db.add_all([self.user, Unit(name='Unit-1'), Unit(name='Unit-2'), Item(name='FCTS6D',project='RELIANCE',family='FCTS'), Item(name='FCTS6D',project='AIRTEL',family='FCTS')]); self.db.flush()
        self.db.add_all([StockTransaction(item_id=i,type=StockTxnType.OPENING,quantity=Decimal(100),date=self.today) for i in (1,2)]);self.db.commit()
    def tearDown(self):
        self.db.close(); self.engine.dispose()
    def count(self,model): return self.db.scalar(select(func.count()).select_from(model))
    def stock(self,i): return dispatches._available_stock(self.db,i)
    def plan_lines(self,items=(1,2),qty=80):
        return [dict(item_id=i,unit_id=1,quantity=qty,planned_date=self.today+timedelta(days=20),planned_end_date=self.today+timedelta(days=22)) for i in items]
    def plans(self,items=(1,2)):
        return planning.create_plan_batch(self.db,DispatchPlanCreateBatch(lines=self.plan_lines(items)))
    def batch(self,plans,quantities):
        return dispatches.record_dispatch_batch(self.db,DispatchBatchCreate(unit_id=1,lines=[dict(plan_id=p.id,quantity=q) for p,q in zip(plans,quantities)]))
    def test_shared_invoice_stock_and_fulfilment(self):
        plans=self.plans(); rows=self.batch(plans,[30,45]);self.assertEqual(rows[0].invoice_number,rows[1].invoice_number)
        self.assertEqual(self.stock(1),70);self.assertEqual(self.stock(2),55)
        self.assertEqual(self.db.get(DispatchPlan,plans[0].id).fulfilled_quantity,30)
        self.assertEqual(self.count(SalesRecord),2)
        sale=dispatches.list_sales(self.db,date_from=self.today,date_to=self.today,limit=None);self.assertEqual(sum(x.quantity for x in sale),75)
        single=dispatches.record_dispatch(self.db,DispatchCreate(plan_id=plans[0].id,unit_id=1,quantity=10,dispatch_date=self.today));self.assertNotEqual(single.invoice_number,rows[0].invoice_number)
    def test_invalid_second_line_rolls_back_everything(self):
        plans=self.plans()
        with self.assertRaises(AppError):self.batch(plans,[30,81])
        self.assertEqual(self.count(Dispatch),0);self.assertEqual(self.count(SalesRecord),0);self.assertEqual(self.stock(1),100);self.assertEqual(self.stock(2),100)
        self.assertEqual(self.db.get(DispatchPlan,plans[0].id).fulfilled_quantity,0)
    def test_combined_same_item_stock_guard(self):
        plans=self.plans((1,1))
        with self.assertRaises(AppError):self.batch(plans,[60,60])
        self.assertEqual(self.stock(1),100);self.assertEqual(self.count(Dispatch),0)
    def test_plan_batches_rollback(self):
        with self.assertRaises(AppError):planning.create_plan_batch(self.db,DispatchPlanCreateBatch(lines=self.plan_lines((1,999))))
        self.assertEqual(self.count(DispatchPlan),0)
        lines=[{k:v for k,v in r.items() if k!='unit_id'} for r in self.plan_lines((1,999))]
        with self.assertRaises(AppError):purchases.create_plan_batch(self.db,PurchasePlanCreateBatch(lines=lines),recorded_by=self.user)
        self.assertEqual(self.count(PurchasePlan),0); self.assertEqual(self.stock(1),100)
        lines[1]['item_id']=2;plans=purchases.create_plan_batch(self.db,PurchasePlanCreateBatch(lines=lines),recorded_by=self.user);self.assertEqual(len(plans),2);self.assertEqual(self.stock(1),100)
    def test_purchase_and_rejection_stock(self):
        pp=purchases.create_plan_batch(self.db,PurchasePlanCreateBatch(lines=[{k:v for k,v in r.items() if k!='unit_id'} for r in self.plan_lines()]),recorded_by=self.user)
        purchases.create_purchase(self.db,PurchaseCreate(lines=[dict(item_id=1,plan_id=pp[0].id,quantity=20),dict(item_id=2,plan_id=pp[1].id,quantity=30)]),recorded_by=self.user)
        self.assertEqual(self.stock(1),120);self.assertEqual(self.stock(2),130)
        purchases.create_purchase_rejection_batch(self.db,PurchaseRejectionBatchCreate(rgp_number='PR/01',lines=[dict(item_id=1,plan_id=pp[0].id,quantity=2)]),recorded_by=self.user)
        plans=self.plans(); delivered=self.batch(plans,[10,10])
        rows=rejections.record_rejection_batch(self.db,RejectionBatchCreate(rgp_number='RGP/01',unit_id=1,rejection_date=self.today,lines=[dict(item_id=2,dispatch_id=delivered[1].id,quantity=3)]),recorded_by=self.user)
        self.assertEqual(rows[0].project,'AIRTEL');self.assertEqual(self.stock(1),110);self.assertEqual(self.stock(2),120)
    def test_po_more_than_four_units(self):
        self.db.add_all([Unit(name=f'Unit-{i}') for i in range(3,7)]);self.db.commit()
        po=purchase_orders.create_purchase_order(self.db,PurchaseOrderCreate(po_number='00012345',po_date=self.today,unit_ids=list(range(1,7)),lines=[dict(item_id=1,quantity=100)]))
        self.assertEqual(po.po_number,'00012345');self.assertEqual(len(po.unit_ids),6);self.assertEqual(po.lines[0].project,'RELIANCE');self.assertEqual(self.stock(1),100)

if __name__=='__main__':unittest.main()
