"""Shared quantity calculations. Only explicit links affect reconciled balances."""
from decimal import Decimal
from sqlalchemy import select, func
from app.models import PurchaseLine, PurchaseRejection, Rejection, SalesRecord
ZERO = Decimal(0)

def linked_sum(model, key, parent):
    return select(func.coalesce(func.sum(model.quantity), 0)).where(key == parent).correlate_except(model).scalar_subquery()

def rejected_for_dispatch(dispatch_id):
    return linked_sum(Rejection, Rejection.dispatch_id, dispatch_id)

def net_sale():
    return SalesRecord.quantity - rejected_for_dispatch(SalesRecord.dispatch_id)

def purchase_balances(db, plan):
    received = db.scalar(select(func.coalesce(func.sum(PurchaseLine.quantity), 0)).where(PurchaseLine.plan_id == plan.id)) or ZERO
    cancelled = db.scalar(select(func.coalesce(func.sum(PurchaseRejection.quantity), 0)).where(PurchaseRejection.plan_id == plan.id)) or ZERO
    return received, cancelled, plan.quantity - received - cancelled
