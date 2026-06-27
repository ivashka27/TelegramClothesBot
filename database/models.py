from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(255))

    gender: Mapped[Optional[str]] = mapped_column(String(20))
    height_cm: Mapped[Optional[int]] = mapped_column(Integer)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    shoe_size: Mapped[Optional[str]] = mapped_column(String(20))
    clothing_size: Mapped[Optional[str]] = mapped_column(String(20))
    age: Mapped[Optional[int]] = mapped_column(Integer)
    body_type: Mapped[Optional[str]] = mapped_column(String(50))

    reference_photo_path: Mapped[Optional[str]] = mapped_column(String(512))
    appearance_description: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    wardrobe_items: Mapped[List["WardrobeItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    outfit_sessions: Mapped[List["OutfitSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    favorite_outfits: Mapped[List["FavoriteOutfit"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WardrobeItem(Base):
    __tablename__ = "wardrobe_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    original_image_path: Mapped[str] = mapped_column(String(512))
    processed_image_path: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="wardrobe_items")


class OutfitSession(Base):
    __tablename__ = "outfit_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    weather_data: Mapped[Optional[str]] = mapped_column(Text)
    selected_item_ids: Mapped[Optional[str]] = mapped_column(Text)
    ai_response: Mapped[Optional[str]] = mapped_column(Text)
    user_feedback: Mapped[Optional[str]] = mapped_column(Text)
    destination: Mapped[Optional[str]] = mapped_column(String(255))
    user_wishes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="outfit_sessions")


class FavoriteOutfit(Base):
    __tablename__ = "favorite_outfits"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    item_ids: Mapped[str] = mapped_column(Text)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="favorite_outfits")
