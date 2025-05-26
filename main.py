from dotenv import load_dotenv
import os
import asyncio
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, ContentType
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from state import Wating
from aiogram.fsm.context import FSMContext
from db import Session, engine
from models import  Student, Base, Admin, Users
from aiogram.types import CallbackQuery
from TEXT import TEXTS
from keyboards import *
from google.genai import types as t
from google import genai
import logging
from google.generativeai import configure, GenerativeModel
from Promt import *
from sqlalchemy import select, exists
from aiogram.filters import StateFilter
from course_data import *
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta



load_dotenv()
session = Session()

dp = Dispatcher()
router = Router()
dp.include_router(router)

BOT_TOKEN = os.getenv("TOKEN_API")

bot = Bot(BOT_TOKEN)

configure(api_key=os.getenv("GEMINI_API_KEY"))   
model = GenerativeModel('gemini-2.0-flash')

processed_messages = set()

ADMIN_IDS = []

@dp.message(Command('start'))
async def starting(message: Message, state: FSMContext):
    print(f"User {message.from_user.id} started the bot")
    
    global ADMIN_IDS
    ADMIN_IDS = [admin.admin_tg for admin in session.query(Admin).all()]
    
    existing_user = session.query(Users).filter_by(user_tg=message.from_user.id).first()
    
    if not existing_user:
        user_data = {
            'user_tg': message.from_user.id,
            'username': message.from_user.username,
            'registration_date': datetime.now()
        }
        
        new_user = Users(**user_data)
        session.add(new_user)
        try:
            session.commit()
            print(f"New user registered: {message.from_user.username or message.from_user.id}")
        except Exception as e:
            session.rollback()
            print(f"Error registering user: {e}")
            # Error message in all languages
            error_msg = ("❌ Registration error. Please try again.\n"
                        "❌ Хатои қайд. Лутфан боз кӯшиш кунед.\n"
                        "❌ Ошибка регистрации. Пожалуйста, попробуйте снова.")
            await message.answer(error_msg)
            return
    
    kb = [
        [KeyboardButton(text=get_text("tajik_btn", "tg"))],
        [KeyboardButton(text=get_text("english_btn", "en")), 
         KeyboardButton(text=get_text("russian_btn", "ru"))]
    ]
    
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    welcome_msg = (
        "🌟 Welcome to SoftClub Bot! 🌟\nPlease choose your language:\n\n"
        "🌟 Хуш омадед ба SoftClub Bot! 🌟\nИлтимос забони худро интихоб кунед:\n\n"
        "🌟 Добро пожаловать в SoftClub Bot! 🌟\nПожалуйста, выберите язык:"
    )
    
    await message.answer(welcome_msg, reply_markup=keyboard)
    await state.set_state(Wating.choosing_language)


@dp.message(Wating.choosing_language)
async def language_selected(message: Message, state: FSMContext):
    if message.text == get_text("english_btn", "en"):
        lang = "en"
    elif message.text == get_text("tajik_btn", "tg"):
        lang = "tg"
    elif message.text == get_text("russian_btn", "ru"):
        lang = "ru"
    else:
        error_msg = (
            "⚠️ Please choose a valid language option.\n\n"
            "⚠️ Илтимос варианти дурустро интихоб кунед.\n\n"
            "⚠️ Пожалуйста, выберите правильный вариант языка."
        )
        await message.answer(error_msg)
        return
    print(f"{message.from_user.username} chose {lang} language")
    
    await state.update_data(language=lang)
    if message.from_user.id in ADMIN_IDS:
        await message.answer(get_text("language_selected", lang), 
                            reply_markup=get_main_menu_for_admin(lang))
    else:
        await message.answer(get_text("language_selected", lang), 
                            reply_markup=get_main_menu(lang))
    await state.set_state(None)





@dp.message(F.text.in_([get_text("announcement", "en"), get_text("announcement", "tg"), get_text("announcement", "ru")]))
async def handle_announcement_command(message: Message, state: FSMContext):
    """
    Handle the announcement command for admins.
    Prompts the admin to enter the announcement content and sets the state.
    """
    user_id = message.from_user.id
    logger.info(f"Announcement command from {message.from_user.username} ({user_id})")
    
    try:
        is_admin = session.query(Admin).filter(Admin.admin_tg == user_id).first() is not None
        if not is_admin:
            lang = (await state.get_data()).get("language", "en")
            await message.answer(get_text("admin_only_action", lang))
            return
    except SQLAlchemyError as e:
        logger.error(f"Database error checking admin: {e}")
        await message.answer(get_text("database_error", lang))
        return

    lang = (await state.get_data()).get("language", "en")
    await message.answer(
        get_text("enter_announcement", lang),
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Wating.waiting_for_announcement)

@dp.message(Wating.waiting_for_announcement, F.content_type.in_({
    ContentType.TEXT, 
    ContentType.PHOTO, 
    ContentType.VIDEO, 
    ContentType.VOICE,
    ContentType.DOCUMENT
}))
async def process_announcement(message: Message, state: FSMContext, bot: Bot):
    """
    Process the announcement content and broadcast it to all users.
    Supports text, photo, video, voice, and document content types.
    """
    lang = (await state.get_data()).get("language", "en")
    logger.info(f"Processing announcement in language: {lang}, content_type: {message.content_type}")

    
    if message.content_type == ContentType.TEXT and not message.text.strip():
        await message.answer(get_text("empty_announcement_error", lang))
        return

    # Fetch all user IDs from the Users table
    try:
        result = session.execute(select(Users.user_tg).where(Users.user_tg.is_not(None)))
        user_ids = result.scalars().unique().all()
        logger.info(f"Found {len(user_ids)} users to send announcement to: {user_ids}")
        if not user_ids:
            await message.answer(
                get_text("no_users_found", lang),
                reply_markup=get_main_menu_for_admin(lang)
            )
            await state.clear()
            return
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        await message.answer(
            get_text("database_error", lang),
            reply_markup=get_main_menu_for_admin(lang)
        )
        await state.clear()
        return

    successful_sends = 0
    failed_sends = 0

    for user_id in user_ids:
        try:
            if message.content_type == ContentType.TEXT:
                formatted_text = get_text("announcement_from_admin", lang, content=message.text.strip())
                logger.debug(f"Sending text to {user_id}: {formatted_text}")
                await bot.send_message(user_id, formatted_text)
            else:
                caption_text = message.caption if message.caption else ""
                formatted_caption = get_text("announcement_from_admin", lang, content=caption_text)
                logger.debug(f"Sending media to {user_id} with caption: {formatted_caption}")

                if message.content_type == ContentType.PHOTO:
                    await bot.send_photo(
                        user_id,
                        message.photo[-1].file_id,
                        caption=formatted_caption or None
                    )
                elif message.content_type == ContentType.VIDEO:
                    await bot.send_video(
                        user_id,
                        message.video.file_id,
                        caption=formatted_caption or None
                    )
                elif message.content_type == ContentType.VOICE:
                    await bot.send_voice(
                        user_id,
                        message.voice.file_id,
                        caption=formatted_caption or None
                    )
                elif message.content_type == ContentType.DOCUMENT:
                    await bot.send_document(
                        user_id,
                        message.document.file_id,
                        caption=formatted_caption or None
                    )
            
            successful_sends += 1
            await asyncio.sleep(0.05)  # Telegram rate limit: ~20 messages/sec

        except Exception as e:
            failed_sends += 1
            logger.error(f"Failed to send to {user_id}: {str(e)}")
            continue

    report_message = (
        f"📊 {get_text('announcement_report', lang)}\n"
        f"✅ {get_text('successful_sends', lang)}: {successful_sends}\n"
        f"❌ {get_text('failed_sends', lang)}: {failed_sends}\n"
        f"👥 {get_text('total_users', lang)}: {len(user_ids)}"
    )
    logger.info(f"Delivery report: {report_message}")
    
    kb = [
        [KeyboardButton(text=get_text("tajik_btn", "tg"))],
        [KeyboardButton(text=get_text("english_btn", "en")), 
         KeyboardButton(text=get_text("russian_btn", "ru"))]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    await message.answer(
        report_message,
        reply_markup=keyboard
    )
    await state.clear()
    await state.set_state(Wating.choosing_language) 

@dp.message(F.text.in_([get_text("my_course", "en"), get_text("my_course", "tg"), get_text("my_course", "ru")]))
async def seeing_courses(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    
    student = session.query(Student).filter(Student.tg_id == message.from_user.id).first()
    if student:
        await message.answer(get_text("already_registered2", lang, course_name=student.course_name), 
                            parse_mode='HTML')
    else:
        await message.answer(get_text("no_courses", lang))

@dp.message(F.text.in_([get_text("view_courses", "en"), get_text("view_courses", "tg"), get_text("view_courses", "ru")]))
async def seeing_courses(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{course['emoji']} {course[f'name_{lang}']}", 
                callback_data=f"course_{course_id}"
            )]
            for course_id, course in courses_data.items()
        ]
    )
    
    await message.answer(get_text("courses_list", lang), reply_markup=inline_kb)

@dp.callback_query(F.data.startswith("course_"))
async def show_course_details(callback: CallbackQuery, state: FSMContext):
    lang = (await state.get_data()).get("language", "en")
    course_id = int(callback.data.split("_")[1])
    course = courses_data.get(course_id)
    
    if not course:
        await callback.answer(get_text("course_not_found", lang))
        return
    
    response = (
        f"<b>{course[f'name_{lang}']}</b>\n\n"
        f"<b>{get_text('what_you_learn', lang)}:</b>\n"
        f"{course[f'what_you_learn_{lang}']}\n\n"
        f"<b>{get_text('duration', lang)}:</b> {course[f'duration_{lang}']}\n"
        f"<b>{get_text('schedule', lang)}:</b> {course[f'schedule_{lang}']}"
    )
    
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.message.answer(response, parse_mode='HTML')
    
    await callback.answer()

@dp.message(F.text.in_([get_text("join_course", "en"), get_text("join_course", "tg"),
                         get_text("join_course", "ru"), get_text("join_course_student", "en"), 
                         get_text("join_course_student", "tg"),get_text("join_course_student", "ru")]))
async def join_course(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    user_id = message.from_user.id
    is_admin = session.query(Admin).filter(Admin.admin_tg == user_id).first() is not None
    if is_admin:
        inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{course['emoji']} {course[f'name_{lang}']}", 
                callback_data=f"join_{course_id}"
            )]
            for course_id, course in courses_data.items()
        ]
    )
    elif not is_admin:
        student = session.query(Student).filter(Student.tg_id == message.from_user.id).first()
        if student:
            await message.answer(get_text("already_registered", lang, course_name=student.course_name),parse_mode='HTML')
            return
        
    await message.answer(get_text("choose_course", lang), reply_markup=inline_kb)

@dp.callback_query(F.data.startswith("join_"))
async def course_selected_for_join(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    course_id = int(callback.data.split("_")[1])
    await state.update_data(course_id=course_id)
    
    lang = (await state.get_data()).get("language", "en")
    await state.set_state(Wating.w_name)
    kb = [
        [KeyboardButton(text=get_text("cancel", lang))],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await callback.message.answer(get_text("enter_fullname", lang), reply_markup=keyboard)


@dp.message(F.text.in_([get_text("cancel", "en"), get_text("cancel", "tg"), get_text("cancel", "ru")]))
async def cancel_registration(message: Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state in [Wating.w_name, Wating.w_phone_num, Wating.w_parents_phone]:
        lang = (await state.get_data()).get("language", "en")
        
        kb = [
            [KeyboardButton(text=get_text("tajik_btn", "tg"))],
            [KeyboardButton(text=get_text("english_btn", "en")), 
             KeyboardButton(text=get_text("russian_btn", "ru"))]
        ]
        keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        
        await message.answer(get_text("registration_canceled", lang), reply_markup=keyboard)
        await state.clear()
        await state.set_state(Wating.choosing_language)

@dp.message(Wating.w_name)
async def insert_name(message: Message, state: FSMContext):
    await state.update_data(fullname=message.text)
    await state.set_state(Wating.w_phone_num)
    lang = (await state.get_data()).get("language", "en")
    await message.answer(get_text("enter_phone", lang))

@dp.message(Wating.w_phone_num)
async def get_phone(message: Message, state: FSMContext):
    if not message.text.isdigit() or len(message.text) < 9 or len(message.text)>12:
        lang = (await state.get_data()).get("language", "en")
        await message.answer(get_text("invalid_phone", lang))
        return
    
    await state.update_data(phone_number=message.text)
    await state.set_state(Wating.w_parents_phone)
    lang = (await state.get_data()).get("language", "en")
    await message.answer(get_text("enter_parents_phone", lang))

@dp.message(Wating.w_parents_phone)
async def get_parents_phone(message: Message, state: FSMContext):
    if not message.text.isdigit() or len(message.text) < 9 or len(message.text) > 13 :
        lang = (await state.get_data()).get("language", "en")
        await message.answer(get_text("invalid_phone", lang))
        return
    
    user_data = await state.get_data()
    course_id = user_data.get("course_id")
    course = courses_data.get(course_id)
    
    new_student = Student(
        tg_id=message.from_user.id,
        fullname=user_data.get("fullname"),
        phone_number=user_data.get("phone_number"),
        second_phone_number=message.text,  
        course_name=course["name_en"] ,
        registration_date= datetime.now() 
    )
    
    session.add(new_student)
    session.commit()
    
    lang = user_data.get("language", "en")
    kb = [
        [KeyboardButton(text=get_text("tajik_btn", "tg"))],
        [KeyboardButton(text=get_text("english_btn", "en")), 
         KeyboardButton(text=get_text("russian_btn", "ru"))]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    await message.answer(
        get_text("registration_success", lang, course_name=course[f"name_{lang}"]),
        reply_markup=keyboard
    )
    await state.clear()
    await state.set_state(Wating.choosing_language)    

print(get_text("setting", "en"))
@dp.message(F.text.in_([get_text("setting", "en"), get_text("setting", "tg"), get_text("setting", "ru")]))
async def setting_command(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    print("Settings command triggered")  
    await message.answer(get_text("setting_answer", lang), 
                       reply_markup=get_setting_menu(lang))
    

@dp.message(F.text.in_([get_text("students", "en"), get_text("students", "tg"), get_text("students", "ru")]))
async def seeing_students(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    user_id = message.from_user.id
    
    try:
        # Check if user is admin
        is_admin = session.query(Admin).filter(Admin.admin_tg == user_id).first() is not None
        if not is_admin:
            await message.answer(get_text("admin_only_action", lang))
            return

        # Calculate date 30 days ago
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        # Query students registered in last 30 days
        recent_students = session.query(Student)\
            .filter(Student.registration_date >= thirty_days_ago)\
            .order_by(Student.registration_date.desc())\
            .all()

        if not recent_students:
            await message.answer(get_text("no_recent_students", lang))
            return

        # Format the response
        response = []
        for student in recent_students:
            reg_date = student.registration_date.strftime("%Y-%m-%d %H:%M")
            response.append(
                f"📅 {reg_date}\n"
                f"👤 {student.fullname}\n"
                f"📱 {student.phone_number}\n"
                f"📱 {student.second_phone_number}\n"
                f"📚 {student.course_name}\n"
                f"━━━━━━━━━━━━━━━━━━"
            )

        # Split into multiple messages if too long
        message_text = get_text("recent_students_header", lang) + "\n\n" + "\n".join(response)
        for chunk in [message_text[i:i+4096] for i in range(0, len(message_text), 4096)]:
            await message.answer(chunk)

    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        await message.answer(get_text("database_error", lang))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await message.answer(get_text("unexpected_error", lang))



@dp.message(F.text.in_([get_text("add_admin", "en"), get_text("add_admin", "tg"), get_text("add_admin", "ru")]))
async def add_admin_command(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    
    if not session.query(Admin).filter(Admin.admin_tg == message.from_user.id).first():
        await message.answer(get_text("admin_only_action", lang))
        return
    
    await message.answer(get_text("enter_username_to_add", lang))
    await state.set_state("waiting_for_admin_name")


@dp.message(F.text, StateFilter("waiting_for_admin_name"))
async def process_admin_name(message: types.Message, state: FSMContext):
    lang = (await state.get_data()).get("language", "en")
    username = message.text.strip()
    
    kb = [
        [KeyboardButton(text=get_text("tajik_btn", "tg"))],
        [KeyboardButton(text=get_text("english_btn", "en")), 
         KeyboardButton(text=get_text("russian_btn", "ru"))]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    if username.startswith('@'):
        username = username[1:]
    
    try:
        try:
            user_tg = int(username)
            user = session.query(Users).filter(Users.user_tg == user_tg).first()
        except ValueError:
            user = session.query(Users).filter(Users.username == username).first()
        
        if not user:
            await message.answer(
                get_text("user_not_found", lang),
                reply_markup=keyboard
            )
            await state.clear()
            await state.set_state(Wating.choosing_language)
            return
        
        if session.query(Admin).filter(Admin.admin_tg == user.user_tg).first():
            await message.answer(
                get_text("user_already_admin", lang),
                reply_markup=keyboard
            )
            await state.clear()
            await state.set_state(Wating.choosing_language)
            return
        
        new_admin = Admin(
            admin_tg=user.user_tg,
            username=user.username,
            last_activity=datetime.now()
        )
        session.add(new_admin)
        session.commit()
        
        try:
            await bot.send_message(
                user.user_tg,
                get_text("you_are_now_admin", lang),
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="/start")]],
                    resize_keyboard=True
                )
            )
        except Exception as e:
            print(f"Couldn't notify new admin: {e}")
        
        display_name = f"@{user.username}" if user.username else f"ID:{user.user_tg}"
        
        await message.answer(
            get_text("admin_added_success", lang).format(
                display_name=display_name
            ),
            reply_markup=keyboard
        )
        print("Admin added successfully")
        
    except Exception as e:
        session.rollback()
        error_msg = get_text("admin_add_error", lang)
        await message.answer(
            error_msg,  
            reply_markup=keyboard
        )
        print(f"Error adding admin: {e}")
    finally:
        await message.answer(get_text("choose_lang_after_add", lang), reply_markup=keyboard)
        await state.clear()
        await state.set_state(Wating.choosing_language)
    
# Delete Admin with Inline Buttons
@dp.message(F.text.in_([get_text("delete_admin", "en"), get_text("delete_admin", "tg"), get_text("delete_admin", "ru")]))
async def delete_admin_command(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    
    # Check if current user is admin
    if not session.query(Admin).filter(Admin.admin_tg == message.from_user.id).first():
        await message.answer(get_text("admin_only_action", lang))
        return
    
    # Get all admins except current
    admins = session.query(Admin).filter(Admin.admin_tg != message.from_user.id).all()
    
    if not admins:
        await message.answer(get_text("no_admins_to_delete", lang))
        return
    
    # Create inline keyboard
    buttons = [
        [types.InlineKeyboardButton(
            text=f"@{admin.username}" if admin.username else f"ID: {admin.admin_tg}",
            callback_data=f"delete_admin_{admin.admin_tg}"
        )] for admin in admins
    ]
    
    buttons.append([types.InlineKeyboardButton(
        text=get_text("cancel_btn", lang),
        callback_data="cancel_admin_delete"
    )])
    
    await message.answer(
        get_text("select_admin_to_delete", lang),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@dp.callback_query(F.data.startswith("delete_admin_"))
async def confirm_delete_admin(callback: types.CallbackQuery, state: FSMContext):
    admin_tg = int(callback.data.split("_")[2])
    lang = (await state.get_data()).get("language", "en")
    
    admin = session.query(Admin).filter(Admin.admin_tg == admin_tg).first()
    if not admin:
        await callback.answer(get_text("admin_not_found", lang))
        return
    
    # Create safe identifier for display
    admin_identifier = f"@{admin.username}" if admin.username else f"ID {admin.admin_tg}"
    
    # Confirmation buttons
    confirm_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=get_text("confirm_btn", lang),
                callback_data=f"confirm_delete_{admin_tg}"
            ),
            types.InlineKeyboardButton(
                text=get_text("cancel_btn", lang),
                callback_data="cancel_admin_delete"
            )
        ]
    ])
    
    # Use a safer text formatting approach
    confirmation_text = (
        get_text("confirm_admin_delete_with_username", lang).format(admin_identifier=admin_identifier)
        if admin.username else
        get_text("confirm_admin_delete_with_id", lang).format(admin_id=admin.admin_tg)
    )
    
    await callback.message.edit_text(
        confirmation_text,
        reply_markup=confirm_kb
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def process_delete_admin(callback: types.CallbackQuery, state: FSMContext):
    admin_tg = int(callback.data.split("_")[2])
    lang = (await state.get_data()).get("language", "en")
    
    try:
        # Get admin info before deletion for notification
        admin = session.query(Admin).filter(Admin.admin_tg == admin_tg).first()
        
        # Delete admin
        deleted_count = session.query(Admin).filter(Admin.admin_tg == admin_tg).delete()
        session.commit()
        
        if deleted_count > 0:
            # Refresh admin list
            global ADMIN_IDS
            ADMIN_IDS = [admin.admin_tg for admin in session.query(Admin).all()]
            
            # Notify removed admin if possible
            if admin:
                try:
                    await bot.send_message(
                        admin_tg,
                        get_text("you_are_removed_admin", lang),
                        reply_markup=ReplyKeyboardMarkup(
                            keyboard=[[KeyboardButton(text="/start")]],
                            resize_keyboard=True
                        )
                    )
                except Exception as e:
                    print(f"Couldn't notify removed admin: {e}")
            
            await callback.message.edit_text(
                get_text("admin_deleted_success", lang),
                reply_markup=None
            )
        else:
            await callback.message.edit_text(get_text("admin_delete_error", lang))
    except Exception as e:
        session.rollback()
        await callback.message.edit_text(get_text("admin_delete_error", lang))
        print(f"Error deleting admin: {str(e)}")
    finally:
        await callback.answer()

# Cancel handler remains the same
@dp.callback_query(F.data == "cancel_admin_delete")
async def cancel_admin_delete(callback: types.CallbackQuery, state: FSMContext):
    lang = (await state.get_data()).get("language", "en")
    await callback.message.edit_text(get_text("admin_delete_canceled", lang))
    await callback.answer()



@dp.message(F.text.in_([get_text("help", "en"), get_text("help", "tg"), get_text("help", "ru")]))
async def help_command(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    await message.answer(get_text("help_menu", lang), reply_markup=get_help_menu(lang))

@dp.message(F.text.in_([get_text("faqbutton", "en"), get_text("faqbutton", "tg"), get_text("faqbutton", "ru")]))
async def faq_menu(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    await message.answer(get_text("faq", lang), reply_markup=get_faq_menu(lang))

@dp.message(F.text.in_([get_text("back", "en"), get_text("back", "tg") , get_text("back", "ru")]))
async def back_to_help(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    await message.answer(get_text("help_menu", lang), reply_markup=get_help_menu(lang))

@dp.message(F.text.in_([get_text("back_to_menu", "en"), get_text("back_to_menu", "tg"), get_text("back_to_menu", "ru")]))
async def back_to_main_menu(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    if message.from_user.id in ADMIN_IDS:
        await message.answer(get_text("main_menu", lang),
                            reply_markup=get_main_menu_for_admin(lang))
    else:
        await message.answer(get_text("main_menu", lang),
                            reply_markup=get_main_menu(lang))

@dp.message(F.text.in_([get_text("main_menu_btn", "en"), get_text("main_menu_btn", "tg"), get_text("main_menu_btn", "ru")]))
async def main_menu(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    if message.from_user.id in ADMIN_IDS:
        await message.answer(get_text("main_menu", lang), 
                            reply_markup=get_main_menu_for_admin(lang))
    else:
        await message.answer(get_text("main_menu", lang), 
                            reply_markup=get_main_menu(lang))




@dp.message(F.text.in_([get_text("faq_items.location", "en"), get_text("faq_items.location", "tg"), get_text("faq_items.location", "ru")]))
async def location_info(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    await message.answer(get_text("location", lang))


@dp.message(F.text.in_([get_text("faq_items.passing_score", "en"), get_text("faq_items.passing_score", "tg"), get_text("faq_items.passing_score", "ru")]))
async def passing_score_info(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    await message.answer(get_text("passing_score", lang))

@dp.message(F.text.in_([get_text("faq_items.frontend_info", "en"), get_text("faq_items.frontend_info", "tg"), get_text("faq_items.frontend_info", "ru")]))
async def frontend_info(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    await message.answer(get_text("frontend_info", lang), parse_mode='HTML')

@dp.message(F.text.in_([get_text("faq_items.backend_info", "en"), get_text("faq_items.backend_info", "tg"), get_text("faq_items.backend_info", "ru")]))
async def backend_info(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    await message.answer(get_text("backend_info", lang), parse_mode='HTML')



users_waiting_queue = []
active_chats = {}  
ADMIN_IDS = []  

admins = session.query(Admin).all()
for admin in admins:
    ADMIN_IDS.append(admin.admin_tg)
print("Active admins:", ADMIN_IDS)

@dp.message(F.text.in_([get_text("contact_support", "en"), get_text("contact_support", "tg"), get_text("contact_support", "ru")]))
async def connect_to_operator(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    
    if message.chat.id in users_waiting_queue:
        await message.answer(get_text("already_in_queue", lang))
        return
    if message.chat.id in active_chats:
        await message.answer(get_text("already_in_chat", lang))
        return

    users_waiting_queue.append(message.chat.id)
    await message.answer(
        get_text("support_request", lang, position=len(users_waiting_queue)),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=get_text("leave_queue_btn", lang))]],
            resize_keyboard=True
        )
    )

    accept_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=get_text("accept_btn", lang), 
        callback_data=f"accept_{message.chat.id}")
    ]])
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message( 
                admin_id,
                get_text("support_request_received", lang, 
                        username=message.from_user.username,
                        user_id=message.chat.id,
                        join_date=datetime.now().strftime("%Y-%m-%d %H:%M")),
                parse_mode='HTML',
                reply_markup=accept_kb
            )
        except Exception as e:
            print(f"Failed to send to admin {admin_id}: {e}")


@dp.callback_query(F.data.startswith('accept_'))
async def accept_connection(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    user_id = int(callback.data.split('_')[1])
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    
    if admin_id in active_chats.values():
        await callback.answer(get_text("admin_busy", lang))
        return
    
    if user_id not in users_waiting_queue:
        await callback.answer(get_text("user_left_queue", lang))
        return

    users_waiting_queue.remove(user_id)
    active_chats[user_id] = admin_id
    active_chats[admin_id] = user_id
    
    user_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=get_text("leave_chat_btn", lang))]],
        resize_keyboard=True
    )
    admin_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=get_text("end_chat_btn", lang))]],
        resize_keyboard=True
    )

    await bot.send_message(
        user_id,
        get_text("connected_with_support", lang),
        parse_mode='HTML',
        reply_markup=user_kb
    )
    
    await callback.message.edit_text(
        get_text("admin_connected", lang, username=callback.from_user.username),
        parse_mode='HTML',
        reply_markup=None
    )
    
    await callback.message.answer(
        get_text("admin_chat_instructions", lang),
        parse_mode='HTML',
        reply_markup=admin_kb
    )
    
    for other_admin in ADMIN_IDS:
        if other_admin != admin_id:
            try:
                await bot.send_message(
                    other_admin,
                    get_text("request_accepted", lang, username=callback.from_user.username),
                    reply_markup=None
                )
            except Exception as e:
                print(f"Failed to notify admin {other_admin}: {e}")


@dp.message(F.text.in_([get_text("leave_queue_btn", "en"), get_text("leave_queue_btn", "tg"), get_text("leave_queue_btn", "ru")]))
async def leave_queue_handler(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    
    if message.chat.id in users_waiting_queue:
        users_waiting_queue.remove(message.chat.id)
        if message.from_user.id in ADMIN_IDS:
            await message.answer(get_text("left_queue", lang), 
                            reply_markup=get_main_menu_for_admin(lang))
        else:
            await message.answer(get_text("left_queue", lang), 
                            reply_markup=get_main_menu(lang))
    elif message.chat.id in active_chats:   
        if message.from_user.id in ADMIN_IDS:
            await message.answer(get_text("no_active_chat", lang), 
                            reply_markup=get_main_menu_for_admin(lang))
        else:
            await message.answer(get_text("no_active_chat", lang), 
                            reply_markup=get_main_menu(lang))                   


@dp.message(F.text.in_([get_text("leave_chat_btn", "en"), get_text("leave_chat_btn", "tg"),
                      get_text("end_chat_btn", "en"), get_text("end_chat_btn", "tg"), get_text("end_chat_btn", "ru"), get_text("leave_chat_btn", "ru")]))
async def leave_chat(message: Message, state: FSMContext):
    user_data = await state.get_data()
    lang = user_data.get("language", "en")
    
    if message.chat.id in users_waiting_queue:
        users_waiting_queue.remove(message.chat.id)
        if message.from_user.id in ADMIN_IDS:
            await message.answer(get_text("left_queue", lang), 
                            reply_markup=get_main_menu_for_admin(lang))
        else:
            await message.answer(get_text("left_queue", lang), 
                            reply_markup=get_main_menu(lang))
                    
    elif message.chat.id in active_chats:
        other_id = active_chats[message.chat.id]
        del active_chats[message.chat.id]
        if other_id in active_chats:
            del active_chats[other_id]
        
        if message.from_user.id in ADMIN_IDS:
            await message.answer(get_text("chat_ended", lang), 
                            reply_markup=get_main_menu_for_admin(lang))
        else:
            await message.answer(get_text("chat_ended", lang), 
                            reply_markup=get_main_menu(lang))

        if message.from_user.id in ADMIN_IDS:
              await bot.send_message(
            other_id,
            get_text("chat_ended", lang),
            reply_markup=get_main_menu_for_admin(lang)
        )
        else:
            await bot.send_message(
            other_id,
            get_text("chat_ended", lang),
            reply_markup=get_main_menu(lang)
        )
                      
    else:
        if message.from_user.id in ADMIN_IDS:
            await message.answer(get_text("no_active_chat", lang), 
                            reply_markup=get_main_menu_for_admin(lang))
        else:
            await message.answer(get_text("no_active_chat", lang), 
                            reply_markup=get_main_menu(lang))        

async def should_skip_ai_response(message: Message, state: FSMContext) -> bool:
    """Check if we should skip AI response for this message"""
    current_state = await state.get_state()
    
    registration_states = [
        Wating.w_name.state,
        Wating.w_phone_num.state,
        Wating.w_parents_phone.state,
        Wating.choosing_language.state,
        Wating.waiting_for_admin_username.state,
        Wating.waiting_for_delete_admin_username.state
        
    ]
    
    if current_state in registration_states:
        return True
        
    button_texts = [
        get_text("my_course", "en"), get_text("my_course", "tg"),
        get_text("view_courses", "en"), get_text("view_courses", "tg"),
        get_text("join_course", "en"), get_text("join_course", "tg"),
        get_text("help", "en"), get_text("help", "tg"),
        get_text("faqbutton", "en"), get_text("faqbutton", "tg"),
        get_text("back", "en"), get_text("back", "tg"),
        get_text("back_to_menu", "en"), get_text("back_to_menu", "tg"),
        get_text("main_menu_btn", "en"), get_text("main_menu_btn", "tg"),
        get_text("contact_support", "en"), get_text("contact_support", "tg"),
    ]
    
    if message.text in button_texts:
        return True
        
    return False


@dp.message(lambda message: message.chat.id in ADMIN_IDS)
async def handle_admin_message(message: Message, state: FSMContext):
    if message.chat.id in active_chats:
        if message.text.lower() == get_text("end_chat_btn", "en").lower() or \
           message.text.lower() == get_text("end_chat_btn", "tg").lower():
            return
        
        user_id = active_chats[message.chat.id]
        await bot.send_message(
            user_id,
            f"👨‍💼 <b>Operator:</b>\n{message.text}",
            parse_mode='HTML'
        )
        return
    
    if await should_skip_ai_response(message, state):
        return
        
    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
        user_data = await state.get_data()
        lang = user_data.get("language", "en")
        user_id2 = message.from_user.id
        response_text  = await generate_ai_response(
        message_text=message.text,
        lang=lang,
        user_id=user_id2
    )
        await message.answer(response_text)
        processed_messages.add(message.message_id)
    except Exception as e:
        logging.error(f"AI Error: {str(e)}")
        await message.answer(get_text("ai_error", lang))

@dp.message()
async def handle_unprocessed_messages(message: Message, state: FSMContext):
    if message.message_id in processed_messages:
        return
    
    if message.chat.id in active_chats:
        if message.text.lower() in [get_text("leave_chat_btn", "en").lower(), 
                                  get_text("leave_chat_btn", "tg").lower()]:
            return
            
        admin_id = active_chats[message.chat.id]
        await bot.send_message(
            admin_id,
            f"👤 <b>{message.from_user.username or 'User'}:</b>\n{message.text}",
            parse_mode='HTML'
        )
        processed_messages.add(message.message_id)
        return
    
    if message.chat.id in users_waiting_queue:
        return
    
    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
        user_id = message.from_user.id
        user_data = await state.get_data()
        lang = user_data.get("language", "en")
        
        response_text  = await generate_ai_response(
        message_text=message.text,
        lang=lang,
        user_id=user_id
    )
        await message.answer(response_text)
        processed_messages.add(message.message_id)
    except Exception as e:
        logging.error(f"AI Error: {str(e)}")
        await message.answer(get_text("ai_error", lang))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())