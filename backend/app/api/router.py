from fastapi import APIRouter

from app.api.routes import (
    auth,
    dashboard,
    operations_reports,
    dispatches,
    items,
    planning,
    purchases,
    purchase_orders,
    rejections,
    stock,
    units,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(units.router)
api_router.include_router(items.router)
api_router.include_router(stock.router)
api_router.include_router(purchase_orders.router)
api_router.include_router(purchases.router)
api_router.include_router(planning.router)
api_router.include_router(dispatches.router)
api_router.include_router(rejections.router)
api_router.include_router(dashboard.router)

api_router.include_router(operations_reports.router)
