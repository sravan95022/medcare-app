from sqlalchemy.orm import Session
from models import AuditLog
from typing import Optional


def log_action(
    db: Session,
    user_id: Optional[int],
    action: str,
    entity: str,
    entity_id: Optional[int] = None,
    details: Optional[str] = None,
):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
    )
    db.add(entry)
    db.commit()
