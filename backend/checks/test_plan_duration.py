"""Category and cross-month regression tests; isolated SQLite only."""
import unittest
from datetime import date, timedelta
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Base, Item, Unit, User, Role, Priority
from app.schemas.planning import DispatchPlanCreate, DispatchPlanUpdate
from app.schemas.purchases import PurchasePlanCreate
from app.schemas.dispatches import DispatchCreate
from app.models import StockTransaction, StockTxnType
from app.services import planning, purchases, dispatches


class DurationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.user = User(username='test',full_name='Test',hashed_password='x',role=Role.ADMIN)
        self.db.add_all([self.user, Item(name='Test',project='Test',family='Test'), Unit(name='Unit-1')])
        self.db.flush()
        self.db.add(StockTransaction(item_id=1,type=StockTxnType.OPENING,quantity=100,date=date(2025,1,1)))
        self.db.commit()
        self.thresholds = patch.multiple(planning.settings,lead_time_normal_days=15,lead_time_urgent_days=7,lead_time_emergency_days=4)
        self.thresholds.start()

    def tearDown(self):
        self.thresholds.stop()
        self.db.close()
        self.engine.dispose()

    def test_boundaries_independent_of_today(self):
        for start in (date(2025,11,24),date(2030,11,24)):
            for days, expected in [(0,Priority.EMERGENCY),(4,Priority.EMERGENCY),(5,Priority.EMERGENCY),(7,Priority.EMERGENCY),(8,Priority.URGENT),(15,Priority.URGENT),(16,Priority.NORMAL),(21,Priority.NORMAL)]:
                with self.subTest(start=start,days=days):
                    self.assertEqual(planning.priority_for_range(start,start+timedelta(days=days)),expected)

    def test_create_and_edit_both_plan_types(self):
        start=date(2025,11,24)
        end=start+timedelta(days=21)
        d=planning.create_dispatch_plan(self.db,DispatchPlanCreate(item_id=1,unit_id=1,quantity=20,planned_date=start,planned_end_date=end,priority=Priority.EMERGENCY))
        p=purchases.create_purchase_plan(self.db,PurchasePlanCreate(item_id=1,quantity=20,planned_date=start,planned_end_date=end),recorded_by=self.user)
        self.assertEqual((d.priority,p.category),(Priority.NORMAL,Priority.NORMAL))
        self.assertFalse(d.warning)
        end=start+timedelta(days=10)
        d=planning.update_dispatch_plan(self.db,d.id,DispatchPlanUpdate(planned_end_date=end,priority=Priority.NORMAL))
        p=purchases.update_purchase_plan(self.db,p.id,PurchasePlanCreate(item_id=1,quantity=20,planned_date=start,planned_end_date=end))
        self.assertEqual((d.priority,p.category),(Priority.URGENT,Priority.URGENT))
        d=planning.update_dispatch_plan(self.db,d.id,DispatchPlanUpdate(planned_end_date=start+timedelta(days=4)))
        self.assertTrue(d.warning)
        self.assertEqual(d.priority,Priority.EMERGENCY)
        d=planning.update_dispatch_plan(self.db,d.id,DispatchPlanUpdate(planned_end_date=start+timedelta(days=5)))
        self.assertFalse(d.warning)

    def test_cross_month_gantt_and_actual_markers(self):
        start=date(2025,11,24); end=date(2025,12,15)
        plan=planning.create_dispatch_plan(self.db,DispatchPlanCreate(item_id=1,unit_id=1,quantity=20,planned_date=start,planned_end_date=end))
        actual=dispatches.record_dispatch(self.db,DispatchCreate(plan_id=plan.id,unit_id=1,quantity=5,dispatch_date=date(2025,12,2)))
        rows=planning.list_gantt_plans(self.db,date_from=date(2025,6,1),date_to=date(2026,5,31))
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0].planned_date,rows[0].planned_end_date),(start,end))
        self.assertEqual(rows[0].actual_dispatches[0].id,actual.id)
        self.assertEqual(rows[0].outstanding_quantity,15)
        december=planning.list_gantt_plans(self.db,date_from=date(2025,12,1),date_to=date(2025,12,31),priority=Priority.NORMAL)
        self.assertEqual([row.id for row in december],[plan.id])

if __name__=='__main__':unittest.main()
