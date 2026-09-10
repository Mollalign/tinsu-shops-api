from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import PhoneAlreadyExistsError, OwnerNotFoundError, IncorrectCurrentPinError
from app.common.security import hash_pin, verify_pin
from app.owners.models import Owner
from app.owners.schemas import OwnerCreate, OwnerResponse


async def create_owner(data: OwnerCreate, db: AsyncSession) -> Owner:
    # Check phone uniqueness
    existing = await db.execute(select(Owner).where(Owner.phone == data.phone))
    if existing.scalar_one_or_none():
        raise PhoneAlreadyExistsError()

    owner = Owner(
        name=data.name,
        phone=data.phone,
        pin_hash=hash_pin(data.pin),
    )
    db.add(owner)
    await db.commit()
    await db.refresh(owner)
    return owner


async def get_owner_by_id(owner_id: UUID, db: AsyncSession) -> Owner:
    result = await db.execute(select(Owner).where(Owner.id == owner_id))
    owner = result.scalar_one_or_none()
    if not owner:
        raise OwnerNotFoundError()
    return owner


async def change_owner_pin(
    owner_id: UUID, current_pin: str, new_pin: str, db: AsyncSession
) -> None:
    """Verify the current PIN then replace it with the new one (hashed)."""
    owner = await get_owner_by_id(owner_id, db)
    if not verify_pin(current_pin, owner.pin_hash):
        raise IncorrectCurrentPinError()
    owner.pin_hash = hash_pin(new_pin)
    await db.commit()
