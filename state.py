from aiogram.fsm.state import State, StatesGroup


class Wating(StatesGroup):
    waiting_for_course_id = State()
    waiting_for_course_id_join = State()
    w_name = State()
    w_phone_num = State()
    w_birhtday = State()
    w_email = State()
    w_parents_phone = State()
    w_adddress = State()
    choosing_language = State()
    waiting_for_ai_question = State()
    waiting_for_admin_username = State()
    waiting_for_delete_admin_username =State()
    waiting_for_announcement = State()

