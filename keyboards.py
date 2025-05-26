from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from TEXT import TEXTS
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Updated get_text function
def get_text(key: str, lang: str, **kwargs) -> str:
    """
    Retrieve a localized string and format it with provided kwargs.
    If no kwargs are provided and the string has placeholders, concatenate without formatting.
    """
    text = TEXTS.get(lang, {}).get(key, key)
    logger.debug(f"get_text: key={key}, lang={lang}, text={text}, kwargs={kwargs}")
    if not kwargs:
        return text  # Return raw text if no kwargs provided
    try:
        return text.format(**kwargs)
    except (IndexError, KeyError) as e:
        logger.warning(f"Formatting error for key={key}, lang={lang}: {e}. Concatenating instead.")
        # Fallback: concatenate content if present, otherwise return text
        content = kwargs.get("content", "")
        return f"{text}{content}".strip() if content else text

# Admin main menu
def get_main_menu_for_admin(lang: str) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text=get_text("view_courses", lang)), 
         KeyboardButton(text=get_text("join_course", lang))],
        [KeyboardButton(text=get_text("help", lang)), 
         KeyboardButton(text=get_text("my_course", lang))],
        [KeyboardButton(text=get_text("setting", lang)),
         KeyboardButton(text=get_text("announcement", lang))],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
def get_text(key: str, lang: str = "en", **kwargs) -> str:
    """Get translated text with formatting"""
    if '.' in key:
        keys = key.split('.')
        value = TEXTS[lang]
        for k in keys:
            value = value.get(k, {})
        return value.format(**kwargs) if isinstance(value, str) else value
    return TEXTS[lang].get(key, key).format(**kwargs)

def get_main_menu(lang: str) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text=get_text("view_courses", lang)), 
         KeyboardButton(text=get_text("join_course", lang))],
        [KeyboardButton(text=get_text("help", lang)), 
         KeyboardButton(text=get_text("my_course", lang))],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_main_menu_for_admin(lang: str) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text=get_text("view_courses", lang)), 
         KeyboardButton(text=get_text("join_course_student", lang))],
        [KeyboardButton(text=get_text("help", lang)), 
         KeyboardButton(text=get_text("students", lang))],
        [ KeyboardButton(text=get_text("setting", lang)),
        KeyboardButton(text=get_text("announcement", lang))],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)



def get_help_menu(lang: str) -> ReplyKeyboardMarkup:
    """Get help menu keyboard based on language"""
    kb = [
        # [KeyboardButton(text="❓ FAQ"), lang],
        [KeyboardButton(text=get_text("faqbutton", lang))],
        [KeyboardButton(text=get_text("contact_support", lang))],
        [KeyboardButton(text=get_text("back_to_menu", lang))]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_setting_menu(lang: str) -> ReplyKeyboardMarkup:
    """Get setting menu keyboard based on language"""
    kb = [
        # [KeyboardButton(text="❓ FAQ"), lang],
        [KeyboardButton(text=get_text("add_admin", lang))],
        [KeyboardButton(text=get_text("delete_admin", lang))],
        [KeyboardButton(text=get_text("back_to_menu", lang))]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_faq_menu(lang: str) -> ReplyKeyboardMarkup:
    """Get FAQ menu keyboard based on language"""
    kb = [
        [KeyboardButton(text=get_text("faq_items.location", lang)), 
         KeyboardButton(text=get_text("faq_items.course_start", lang))],
        [KeyboardButton(text=get_text("faq_items.passing_score", lang)), 
         KeyboardButton(text=get_text("faq_items.backend_info", lang))],
        [KeyboardButton(text=get_text("faq_items.frontend_info", lang)), 
         KeyboardButton(text=get_text("faq_items.design_info", lang))],
        [KeyboardButton(text=get_text("back", lang)), 
         KeyboardButton(text=get_text("main_menu_btn", lang))]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)