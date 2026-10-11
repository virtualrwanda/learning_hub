from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class AuditService:
    @staticmethod
    async def log(
        db: AsyncSession,
        *,
        actor_user_id: UUID | None,
        action: str,
        target_entity_type: str | None = None,
        target_entity_id: UUID | None = None,
        previous_value: dict | None = None,
        new_value: dict | None = None,
        ip_address: str | None = None,
        result: str = "success",
    ) -> None:
        db.add(
            AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                target_entity_type=target_entity_type,
                target_entity_id=target_entity_id,
                previous_value=previous_value,
                new_value=new_value,
                ip_address=ip_address,
                result=result,
            )
        )