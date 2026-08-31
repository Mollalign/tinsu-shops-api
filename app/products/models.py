import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        CheckConstraint("selling_price > 0", name="ck_products_selling_price_positive"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_quantity_non_negative"),
        CheckConstraint(
            "low_stock_threshold >= 0", name="ck_products_low_stock_threshold_non_negative"
        ),
        Index("ix_products_shop_id", "shop_id"),
        Index("ix_products_name", "name"),
        Index("ix_products_shop_id_is_active", "shop_id", "is_active"),
        Index("ix_products_category_id", "category_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="products")  # noqa: F821
    category_obj: Mapped["Category | None"] = relationship(  # noqa: F821
        "Category", back_populates="products", lazy="joined"
    )
    inventory_movements: Mapped[list["InventoryMovement"]] = relationship(  # noqa: F821
        "InventoryMovement", back_populates="product", lazy="select"
    )
    sale_items: Mapped[list["SaleItem"]] = relationship(  # noqa: F821
        "SaleItem", back_populates="product", lazy="select"
    )

    @property
    def category_name(self) -> str | None:
        """Convenience property — populated by the joined category_obj."""
        return self.category_obj.name if self.category_obj else None
