from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BTN_GENERATE = "✨ Сгенерировать наряд на сегодня"
BTN_TWO_VARIANTS = "👔 Два варианта образа"
BTN_WEEK_PLAN = "📅 План на неделю"
BTN_GAPS = "🛒 Чего не хватает"
BTN_ADD_ITEM = "➕ Добавить вещь"
BTN_VIEW_PHOTOS = "👁 Посмотреть фото"
BTN_DELETE_ITEMS = "🗑 Удалить вещи"
BTN_CLEAR_WARDROBE = "🧹 Очистить гардероб"
BTN_WARDROBE = "👗 Мой гардероб"
BTN_PROFILE = "👤 Мой профиль"
BTN_USER_PHOTO = "📸 Моё фото"
BTN_SET_CITY = "📍 Указать город"
BTN_CHECKLIST = "📋 Что настроить"
BTN_HELP = "❓ Помощь"
BTN_EDIT_PROFILE = "✏️ Изменить параметры"
BTN_CANCEL = "❌ Отмена"
BTN_BACK = "◀️ Назад"
BTN_MAIN_MENU = "🏠 В меню"
BTN_FAVORITES = "⭐ Избранные образы"

ALL_MENU_BUTTONS = {
    BTN_GENERATE,
    BTN_TWO_VARIANTS,
    BTN_WEEK_PLAN,
    BTN_GAPS,
    BTN_ADD_ITEM,
    BTN_VIEW_PHOTOS,
    BTN_DELETE_ITEMS,
    BTN_CLEAR_WARDROBE,
    BTN_WARDROBE,
    BTN_PROFILE,
    BTN_USER_PHOTO,
    BTN_SET_CITY,
    BTN_CHECKLIST,
    BTN_HELP,
    BTN_EDIT_PROFILE,
    BTN_CANCEL,
    BTN_BACK,
    BTN_MAIN_MENU,
    BTN_FAVORITES,
}


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_GENERATE), KeyboardButton(text=BTN_TWO_VARIANTS)],
            [KeyboardButton(text=BTN_WEEK_PLAN), KeyboardButton(text=BTN_GAPS)],
            [KeyboardButton(text=BTN_ADD_ITEM), KeyboardButton(text=BTN_VIEW_PHOTOS)],
            [KeyboardButton(text=BTN_DELETE_ITEMS), KeyboardButton(text=BTN_CLEAR_WARDROBE)],
            [KeyboardButton(text=BTN_WARDROBE), KeyboardButton(text=BTN_FAVORITES)],
            [KeyboardButton(text=BTN_PROFILE), KeyboardButton(text=BTN_CHECKLIST)],
            [KeyboardButton(text=BTN_USER_PHOTO), KeyboardButton(text=BTN_SET_CITY)],
            [KeyboardButton(text=BTN_HELP)],
            [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_MAIN_MENU)],
        ],
        resize_keyboard=True,
    )


def outfit_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Другой образ", callback_data="outfit:regenerate"),
                InlineKeyboardButton(text="⭐ В избранное", callback_data="outfit:favorite"),
            ],
            [
                InlineKeyboardButton(text="👔 Менее официально", callback_data="outfit:adj:casual"),
                InlineKeyboardButton(text="🧥 Теплее", callback_data="outfit:adj:warmer"),
            ],
        ]
    )


def after_add_item_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить ещё", callback_data="wardrobe:add"),
                InlineKeyboardButton(text="👗 Мой гардероб", callback_data="wardrobe:list"),
            ],
        ]
    )


def clear_wardrobe_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить всё", callback_data="wardrobe:clear:yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="wardrobe:clear:no"),
            ],
        ]
    )


def user_photo_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Заменить фото", callback_data="user_photo:replace"),
                InlineKeyboardButton(text="🗑 Удалить фото", callback_data="user_photo:delete"),
            ],
        ]
    )


def favorites_delete_keyboard(favs: list) -> InlineKeyboardMarkup:
    rows = []
    for fav in favs[:10]:
        label = f"🗑 {fav.title}"
        if len(label) > 64:
            label = label[:61] + "…"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"fav:del:{fav.id}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
