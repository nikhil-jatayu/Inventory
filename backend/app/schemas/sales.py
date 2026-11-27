from datetime import date

from app.schemas.common import APIModel, Quantity


class SalesRecordOut(APIModel):
    id: int
    dispatch_id: int
    plan_id: int | None
    invoice_number: str
    invoice_date: date
    po_number: str | None
    item_id: int
    item_name: str
    project: str
    family: str
    unit_id: int | None
    unit_name: str | None
    quantity: Quantity
    rejected_quantity: Quantity = 0
    net_quantity: Quantity = 0
