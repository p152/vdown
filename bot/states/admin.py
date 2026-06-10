from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_group_id = State()
