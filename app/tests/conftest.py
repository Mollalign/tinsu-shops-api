"""
Pytest configuration and shared fixtures.
Uses an in-memory SQLite database via aiosqlite for fast, isolated tests.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.common.security import hash_pin
from app.database import Base, get_db
from app.main import create_app


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    TestingSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# App + HTTP client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def app_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app: FastAPI = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Helper: create owner directly in DB
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def owner(db_session: AsyncSession):
    from app.owners.models import Owner
    o = Owner(name="Tinsu", phone="0912345678", pin_hash=hash_pin("1234"))
    db_session.add(o)
    await db_session.commit()
    await db_session.refresh(o)
    return o


@pytest_asyncio.fixture
async def owner_token(app_client: AsyncClient, owner) -> str:
    resp = await app_client.post(
        "/api/v1/auth/owner/login", json={"phone": "0912345678", "pin": "1234"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def shop(db_session: AsyncSession, owner):
    from app.shops.models import Shop
    s = Shop(owner_id=owner.id, name="Main Shop", location="Halaba")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def worker(db_session: AsyncSession, shop):
    from app.workers.models import Worker
    w = Worker(shop_id=shop.id, name="Hana", pin_hash=hash_pin("5678"))
    db_session.add(w)
    await db_session.commit()
    await db_session.refresh(w)
    return w


@pytest_asyncio.fixture
async def worker_token(app_client: AsyncClient, shop, worker) -> str:
    resp = await app_client.post(
        "/api/v1/auth/worker/login",
        json={
            "shop_id": str(shop.id),
            "worker_id": str(worker.id),
            "pin": "5678",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def product(db_session: AsyncSession, shop):
    from decimal import Decimal
    from app.products.models import Product
    p = Product(
        shop_id=shop.id,
        name="Coca-Cola 500ml",
        selling_price=Decimal("35.00"),
        stock_quantity=50,
        low_stock_threshold=5,
        category="Drinks",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p
