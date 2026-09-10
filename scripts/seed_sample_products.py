"""Insert sample categories + products into every active shop.

Safe to re-run: existing names are updated (photo_url) rather than duplicated.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import func, select

import app.categories.models  # noqa: F401
import app.inventory.models  # noqa: F401
import app.owners.models  # noqa: F401
import app.products.models  # noqa: F401
import app.sales.models  # noqa: F401
import app.shops.models  # noqa: F401
import app.workers.models  # noqa: F401

from app.categories.models import Category
from app.common.enums import ActorType, InventoryMovementType
from app.database import AsyncSessionLocal
from app.inventory.models import InventoryMovement
from app.owners.models import Owner
from app.products.models import Product
from app.shops.models import Shop

def _img(photo_id: str) -> str:
    return (
        f"https://images.unsplash.com/{photo_id}"
        "?auto=format&fit=crop&w=400&h=400&q=80"
    )


# name, price, stock, low_stock_threshold, photo_url
SAMPLE_CATALOG: dict[str, list[tuple[str, str, int, int, str]]] = {
    "Drinks": [
        ("Coca-Cola 500ml", "35.00", 24, 5, _img("photo-1554866585-cd94860890b7")),
        ("Water 500ml", "20.00", 40, 8, _img("photo-1548839140-29a749e1cf4d")),
        ("Fanta 500ml", "35.00", 18, 5, _img("photo-1624517452488-04869289c4ca")),
        ("Sprite 500ml", "35.00", 16, 5, _img("photo-1625772299848-391b6a87d7b3")),
        ("Pepsi 500ml", "30.00", 12, 5, _img("photo-1629203851122-3726ecdf080e")),
    ],
    "Snacks": [
        ("Biscuit", "15.00", 30, 8, _img("photo-1558961363-fa8fdf82db35")),
        ("Chips", "25.00", 20, 5, _img("photo-1566478989037-eec170784d0b")),
        ("Chocolate", "40.00", 10, 3, _img("photo-1511381939415-d513ac7e49d5")),
    ],
    "Food": [
        ("Bread", "15.00", 12, 4, _img("photo-1509440159596-0249088772ff")),
        ("Eggs (6 pack)", "90.00", 8, 3, _img("photo-1582722872445-44dc5f7e3c8f")),
        ("Pasta 500g", "45.00", 15, 4, _img("photo-1621996346565-e3dbc646d9a9")),
    ],
    "Other": [
        ("Soap", "25.00", 10, 3, _img("photo-1584305574647-0cc949a2e9ea")),
        ("Tissue", "20.00", 14, 4, _img("photo-1584555613497-6ec5055e1c2e")),
    ],
}


async def _get_or_create_category(
    db, shop_id, name: str
) -> Category:
    existing = await db.scalar(
        select(Category).where(
            Category.shop_id == shop_id,
            func.lower(Category.name) == name.lower(),
        )
    )
    if existing:
        return existing
    category = Category(shop_id=shop_id, name=name)
    db.add(category)
    await db.flush()
    return category


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        shops = (
            await db.execute(
                select(Shop).where(Shop.is_active.is_(True)).order_by(Shop.created_at)
            )
        ).scalars().all()

        if not shops:
            print("No active shops found. Create a shop first, then re-run.")
            return

        for shop in shops:
            owner = await db.get(Owner, shop.owner_id)
            print(f"Seeding shop: {shop.name}")

            created = 0
            updated = 0
            for category_name, products in SAMPLE_CATALOG.items():
                category = await _get_or_create_category(db, shop.id, category_name)
                for name, price, stock, threshold, photo_url in products:
                    existing = await db.scalar(
                        select(Product).where(
                            Product.shop_id == shop.id,
                            func.lower(Product.name) == name.lower(),
                        )
                    )
                    if existing:
                        existing.photo_url = photo_url
                        existing.category_id = category.id
                        updated += 1
                        continue

                    product = Product(
                        shop_id=shop.id,
                        category_id=category.id,
                        name=name,
                        selling_price=Decimal(price),
                        stock_quantity=stock,
                        low_stock_threshold=threshold,
                        photo_url=photo_url,
                        is_active=True,
                    )
                    db.add(product)
                    await db.flush()

                    if stock > 0:
                        db.add(
                            InventoryMovement(
                                shop_id=shop.id,
                                product_id=product.id,
                                type=InventoryMovementType.INITIAL,
                                quantity=stock,
                                reason="Sample seed stock",
                                created_by_type=ActorType.OWNER,
                                created_by_id=owner.id if owner else None,
                            )
                        )
                    created += 1

            await db.commit()
            print(f"  created={created} photos_updated={updated}")

        print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())
