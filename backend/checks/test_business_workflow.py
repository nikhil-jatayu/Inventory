"""Service regression tests in a fresh in-memory DB, never the configured DB."""
import unittest
from datetime import date,timedelta
from decimal import Decimal
from io import BytesIO
from sqlalchemy import create_engine, select, func, event
from sqlalchemy.orm import Session
from app.models import Base, Item, Unit, User, Role, StockTransaction, StockTxnType, PurchasePlan, PurchaseLine, PurchaseRejection, Rejection, RejectionIssue, SalesRecord, DispatchPlan
from app.schemas.purchases import PurchasePlanCreate, PurchaseCreate, PurchaseRejectionBatchCreate, PurchaseRejectionCreate
from app.schemas.planning import DispatchPlanCreate
from app.schemas.dispatches import DispatchCreate
from app.schemas.rejections import RejectionCreate, RejectionBatchCreate
from app.services import purchases,rejections,dispatches,planning,dashboard
from app.services.operations_reports import build_report, REPORTS
from app.services.report_exports import xlsx,pdf
from app.core.errors import AppError
from app.core.fiscal import fiscal_label,fiscal_start_year

class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://')
        @event.listens_for(self.engine,'connect')
        def fk(conn,_): conn.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine,autoflush=False,expire_on_commit=False)
        self.today=date.today(); self.user=User(username='u',full_name='Test',hashed_password='x',role=Role.ADMIN)
        self.db.add_all([self.user,Item(name='FCTS6D',project='RELIANCE',family='FCTS'),Item(name='FCTS6D',project='AIRTEL',family='FCTS'),Unit(name='Unit-1'),Unit(name='Unit-2')]);self.db.flush()
        self.db.add_all([StockTransaction(item_id=i,type=StockTxnType.OPENING,quantity=100,date=self.today-timedelta(days=40)) for i in (1,2)]);self.db.commit()
    def tearDown(self):self.db.close();self.engine.dispose()
    def count(self,m):return self.db.scalar(select(func.count()).select_from(m))
    def stock(self,i):return dispatches._available_stock(self.db,i)
    def pp(self,i=1,q=100):return purchases.create_purchase_plan(self.db,PurchasePlanCreate(item_id=i,quantity=q,planned_date=self.today,planned_end_date=self.today+timedelta(days=4)),recorded_by=self.user)
    def receive(self,lines):return purchases.create_purchase(self.db,PurchaseCreate(lines=lines),recorded_by=self.user)
    def cancel(self,lines):return purchases.create_purchase_rejection_batch(self.db,PurchaseRejectionBatchCreate(rgp_number='PR/TEST',lines=lines),recorded_by=self.user)
    def delivery(self,i=1,u=1,q=60,d=None):
        d=d or self.today
        p=planning.create_dispatch_plan(self.db,DispatchPlanCreate(item_id=i,unit_id=u,quantity=q,planned_date=d,planned_end_date=d))
        return dispatches.record_dispatch(self.db,DispatchCreate(plan_id=p.id,unit_id=u,quantity=q,dispatch_date=d))
    def reject(self,lines,u=1,d=None):return rejections.record_rejection_batch(self.db,RejectionBatchCreate(rgp_number='RGP/TEST',unit_id=u,rejection_date=d or self.today,lines=lines),recorded_by=self.user)
    def report(self,kind='management',**kwargs):return build_report(self.db,kind=kind,date_from=self.today.replace(day=1),date_to=self.today+timedelta(days=20),**kwargs)
    def test_purchase_balance_and_stock(self):
        p=self.pp();self.receive([dict(item_id=1,plan_id=p.id,quantity=35)]);self.cancel([dict(item_id=1,plan_id=p.id,quantity=15)])
        row=purchases.list_purchase_plans(self.db)[0];self.assertEqual((row.received_quantity,row.cancelled_quantity,row.outstanding_quantity,row.status),(35,15,50,'PARTIAL'));self.assertEqual(self.stock(1),135)
        self.cancel([dict(item_id=1,plan_id=p.id,quantity=50)]);row=purchases.list_purchase_plans(self.db)[0];self.assertEqual(row.status,'CLOSED');self.assertEqual(row.outstanding_quantity,0)
        with self.assertRaises(AppError):self.receive([dict(item_id=1,plan_id=p.id,quantity=1)])
        self.assertEqual(self.stock(1),135)
    def test_purchase_full_cancellation_and_no_delete(self):
        p=self.pp();r=purchases.create_purchase_rejection(self.db,PurchaseRejectionCreate(rgp_number='PR/FULL',plan_id=p.id,item_id=1,quantity=100),recorded_by=self.user);self.assertEqual(r.plan_id,p.id)
        self.assertEqual(purchases.list_purchase_plans(self.db)[0].status,'CANCELLED');self.assertEqual(self.stock(1),100)
        with self.assertRaises(AppError):purchases.cancel_purchase_plan(self.db,p.id)
        with self.assertRaises(AppError):purchases.update_purchase_plan(self.db,p.id,PurchasePlanCreate(item_id=1,quantity=101,planned_date=self.today,planned_end_date=self.today+timedelta(days=4)))
        self.assertEqual(self.count(PurchasePlan),1)
    def test_receipt_and_cancel_invalid_second_line_rollback(self):
        a,b=self.pp(),self.pp(2)
        for operation in (self.receive,self.cancel):
            with self.assertRaises(AppError):operation([dict(item_id=1,plan_id=a.id,quantity=20),dict(item_id=2,plan_id=b.id,quantity=101)])
        self.assertEqual(self.count(PurchaseLine),0);self.assertEqual(self.count(PurchaseRejection),0);self.assertEqual(self.stock(1),100)
    def test_multiple_plans_same_item(self):
        a,b=self.pp(),self.pp();result=self.receive([dict(item_id=1,plan_id=a.id,quantity=20),dict(item_id=1,plan_id=b.id,quantity=30)])
        self.assertEqual(len(result.lines),2);self.assertEqual(self.stock(1),150)
    def test_unit_rejection_no_issue_no_stock_no_reopen(self):
        a=self.delivery();r=self.reject([dict(item_id=1,dispatch_id=a.id,quantity=15)])[0];self.assertIsNone(r.issue_id);self.assertEqual(self.count(RejectionIssue),0);self.assertEqual(self.stock(1),40)
        sale=dispatches.list_sales(self.db)[0];self.assertEqual((sale.quantity,sale.rejected_quantity,sale.net_quantity),(60,15,45));self.assertEqual(self.db.get(DispatchPlan,a.plan_id).fulfilled_quantity,60)
        self.assertEqual(rejections.list_rejections(self.db,search=None,date_from=None,date_to=None,family=None,issue_id=None,sort='rejection_date',order='desc',page=1,page_size=20).total,1)
        with self.assertRaises(AppError):self.reject([dict(item_id=1,dispatch_id=a.id,quantity=46)])
        self.assertEqual(self.count(Rejection),1)
    def test_rejection_wrong_unit_item_and_atomic(self):
        a,b=self.delivery(),self.delivery(i=2)
        with self.assertRaises(AppError):self.reject([dict(item_id=1,dispatch_id=a.id,quantity=10)],u=2)
        with self.assertRaises(AppError):self.reject([dict(item_id=2,dispatch_id=a.id,quantity=10)])
        with self.assertRaises(AppError):self.reject([dict(item_id=1,dispatch_id=a.id,quantity=10),dict(item_id=2,dispatch_id=b.id,quantity=61)])
        with self.assertRaises(AppError):self.reject([dict(item_id=1,dispatch_id=a.id,quantity=10)],d=self.today-timedelta(days=1))
        self.assertEqual(self.count(Rejection),0);self.assertEqual(sum(r.net_quantity for r in dispatches.list_sales(self.db)),120)
    def test_rejection_adjusts_original_invoice_month(self):
        previous=self.today.replace(day=1)-timedelta(days=1);a=self.delivery(d=previous)
        self.reject([dict(item_id=1,dispatch_id=a.id,quantity=15)])
        sale=dispatches.list_sales(self.db,date_from=previous.replace(day=1),date_to=previous)[0];self.assertEqual(sale.net_quantity,45)
        result=dashboard.get_dashboard(self.db,month=previous.strftime('%Y-%m'),fy=None,family=None);self.assertEqual(result.kpis.month_sales,45);self.assertEqual(result.kpis.month_rejected,0)
        report=dispatches.get_dispatch_report(self.db,fy=fiscal_label(fiscal_start_year(previous)),family=None);self.assertEqual(report.total_sales,45)
    def test_legacy_unlinked_not_subtracted(self):
        a=self.delivery();self.db.add(Rejection(item_id=1,unit_id=1,rgp_number='OLD',rejection_date=self.today,quantity=8,recorded_by=self.user.id));self.db.commit()
        self.assertEqual(dispatches.list_sales(self.db)[0].net_quantity,60)
        metrics={m['label']:m['value'] for m in self.report()['metrics']};self.assertEqual(metrics['Unallocated unit rejections in period'],8);self.assertEqual(metrics['Net sales'],60)
    def test_all_reports_exports_and_filters(self):
        p=self.pp();self.receive([dict(item_id=1,plan_id=p.id,quantity=20)]);self.cancel([dict(item_id=1,plan_id=p.id,quantity=10)]);a=self.delivery();self.reject([dict(item_id=1,dispatch_id=a.id,quantity=5)])
        for kind in REPORTS:
            data=self.report(kind);self.assertTrue(data['sections']);self.assertTrue(xlsx(data).startswith(b'PK'));self.assertTrue(pdf(data).startswith(b'%PDF-'))
        from openpyxl import load_workbook
        data=self.report('sales',project='RELIANCE',unit_id=1);metrics={m['label']:m['value'] for m in data['metrics']};self.assertEqual(metrics['Net sales'],55)
        book=load_workbook(BytesIO(xlsx(data)));self.assertGreaterEqual(len(book.sheetnames),2);self.assertEqual(book.worksheets[1]['J2'].value,55)
        with self.assertRaises(AppError):self.report('stock',unit_id=1)
    def test_rejection_single_endpoint_no_fallback(self):
        a=self.delivery();r=rejections.record_rejection(self.db,RejectionCreate(rgp_number='RGP/SINGLE',dispatch_id=a.id,unit_id=1,item_id=1,quantity=4,rejection_date=self.today),recorded_by=self.user);self.assertEqual(r.dispatch_id,a.id);self.assertIsNone(r.issue_name)

if __name__=='__main__':unittest.main()
