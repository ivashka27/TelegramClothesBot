from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    waiting_city = State()
    waiting_outfit_details = State()
    waiting_add_item_photo = State()
    waiting_view_items = State()
    waiting_delete_items = State()
    waiting_user_photo = State()
    waiting_profile_field = State()
    waiting_clear_confirm = State()
