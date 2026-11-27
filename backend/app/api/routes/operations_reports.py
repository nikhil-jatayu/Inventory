from datetime import date
from typing import Annotated, Literal
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.services.operations_reports import build_report
from app.services import report_exports

router=APIRouter(tags=['operations reports'])
@router.get('/reports/operations')
def operations_report(_:Annotated[User,Depends(get_current_user)],db:Annotated[Session,Depends(get_db)],kind:str,date_from:date,date_to:date,project:str|None=None,family:str|None=None,item_id:int|None=None,unit_id:int|None=None,format:Literal['json','xlsx','pdf']='json'):
    # Repeatable-read snapshot prevents a concurrent receipt/rejection from splitting report totals.
    # Auth may have already opened a transaction, so use a dedicated read-only session for PostgreSQL.
    if db.bind.dialect.name=='postgresql':
        with db.bind.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            with Session(bind=conn) as read_db:
                data=build_report(read_db,kind=kind,date_from=date_from,date_to=date_to,project=project,family=family,item_id=item_id,unit_id=unit_id)
    else:
        data=build_report(db,kind=kind,date_from=date_from,date_to=date_to,project=project,family=family,item_id=item_id,unit_id=unit_id)
    if format=='json':return jsonable_encoder(data)
    content=report_exports.xlsx(data) if format=='xlsx' else report_exports.pdf(data)
    media='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if format=='xlsx' else 'application/pdf'
    return Response(content,media_type=media,headers={'Content-Disposition':f'attachment; filename="inventory-{kind}-{date_from}.{format}"'})
