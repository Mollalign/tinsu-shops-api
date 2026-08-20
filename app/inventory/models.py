import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.enums import ActorType, InventoryMovementType
from app.database import Base


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    __table_args__ = (
        Index("ix_inventory_movements_shop_id", "shop_id"),
        Index("ix_inventory_movements_product_id", "product_id"),
        Index("ix_inventory_movements_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[InventoryMovementType] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # positive or negative
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_type: Mapped[ActorType] = mapped_column(nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    product: Mapped["Product"] = relationship(  # noqa: F821
        "Product", back_populates="inventory_movements"
    )
