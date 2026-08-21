import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.enums import ActorType
from app.database import Base


class Sale(Base):
    __tablename__ = "sales"

    __table_args__ = (
        Index("ix_sales_shop_id", "shop_id"),
        Index("ix_sales_created_at", "created_at"),
        Index("ix_sales_sold_by_id", "sold_by_id"),
        Index("ix_sales_shop_id_created_at", "shop_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sold_by_type: Mapped[ActorType] = mapped_column(nullable=False)
    sold_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Kept nullable — historical rows may have a value; new sales do not use it
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)

    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Idempotency — prevents duplicate sales on mobile retry
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )

    # Relationships
    items: Mapped[list["SaleItem"]] = relationship(
        "SaleItem", back_populates="sale", lazy="select", cascade="all, delete-orphan"
    )


class SaleItem(Base):
    __tablename__ = "sale_items"

    __table_args__ = (
        Index("ix_sale_items_sale_id", "sale_id"),
        Index("ix_sale_items_product_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Relationships
    sale: Mapped["Sale"] = relationship("Sale", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="sale_items")  # noqa: F821
