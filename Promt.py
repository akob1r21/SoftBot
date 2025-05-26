from dotenv import load_dotenv
import os
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime
from keyboards import *
from google.generativeai import configure, GenerativeModel
from typing import Dict, List
from aiogram.fsm.storage.memory import MemoryStorage
from course_data import *
from datetime import datetime, timedelta
from typing import Dict, List
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

configure(api_key=os.getenv("GEMINI_API_KEY"))  
model = GenerativeModel('gemini-2.0-flash')

def get_course_start_date():
    today = datetime.now()
    current_day = today.day

    if current_day < 5:
        month_name = today.strftime("%B")
        return f"5th of this month ({month_name})"
    else:
        next_month = today.replace(day=28) + timedelta(days=4)
        month_name = next_month.strftime("%B")
        return f"5th of next month ({month_name})"



class ConversationHistory:
    def __init__(self):
        self.history: Dict[int, List[Dict[str, str]]] = {} 
    
    def add_message(self, user_id: int, role: str, content: str):
        if user_id not in self.history:
            self.history[user_id] = []
        self.history[user_id].append({"role": role, "content": content})
        
        if len(self.history[user_id]) > 5:
            print(self.history[user_id])
            self.history[user_id] = self.history[user_id][-5:]
            print(self.history[user_id])

    
    def get_history(self, user_id: int) -> List[Dict[str, str]]:
        print(self.history[user_id])
        return self.history.get(user_id, [])


storage = MemoryStorage()
conversation_history = ConversationHistory()

AI_PROMPT_TEMPLATE = """
try speak in language user speak its can be be tajik english and russian
You are a helpful assistant for a programming education bot called SoftClub.
You provide helpful, concise answers to questions about our courses and programs.
You are not a human, you are a bot.
dont introduce urself always just one time when greetings or when user ask you
You are an assistant by name Softbot at Softclub programming academy
users usually speak in tajik see what language they use and talk
with that language if they write салом speak in tajik with them.
If you couldnt find answer for any question and question depends about programming 
or our academy or courses say in their languages "Sorry, I don't know, you can connect with
operator using help button." if it doesnt depend about
programming or our academy or courses say "Sorry, I can only help you get information about our academy,"
Provide helpful, concise answers to questions about our courses and programs.
If the message isn't a question, respond politely asking how you can help.
And just introduce yourself one time when user ask you or when greetings not every time and say i am 
Softbot how can i help you.
Previous conversation:
{conversation_history}

Current message: {message_text}

[Rest of your existing prompt template...]

Course information:
- course_start: "📢 New courses start on {course_start_date} but we have free lesson on
 4th on that month u can participate"
- passing_score: "📊 The minimum passing score is 80%"
- frontend_info: "💻 <b>Frontend  Course Structure:</b>\n\n1️⃣ First Month: C++ Fundamentals\n2️⃣ Second Month: HTML/CSS Basics\n3️⃣ Third Month: GitHub & Functions\n4️⃣ Fourth Month +: JavaScript"
- backend_info: "🖥️ <b>Backend Development Course Structure:</b>\n\n1️⃣ First Month: C++ Fundamentals\n2️⃣ Second Month: HTML/CSS Basics\n3️⃣ Third Month: GitHub & Functions\n4️⃣ Fourth Month +: C# or Python"
- location: "🏫 Our address:\nRahimi Street, Dushanbe, Tajikistan\n\n📍 <a href=' Softclub in Google Maps (https://maps.app.goo.gl/FTa6oGyyLEpmE8YL7)/'>View on Map</a>"

Our courses include:
{formatted_courses}

Registration process:
{registration_info}
Key rules:
1. Language: Match user's language "try to use emojes to look best 😊 not only this one 
other emojes too depend to conversation u have"
2. For compliments/thanks: Respond warmly but briefly (e.g. "Thank you! 😊")
3. For greetings: Respond appropriately (e.g. "Hello! How can I help?")
4. For questions: Provide concise, helpful answers about:
   - Courses starting: {course_start_date} (free lesson on 4th)
   - Available courses: {formatted_courses}
   - Location: Rahimi Street, Dushanbe
5. For unclear messages: Ask "Could you clarify?"
6. Never repeat user's words back
7. Keep responses under 3 sentences

Examples:
User: "You're great!" 
You: "Thank you! Happy to help 😊"

IMPORTANT RULES:
1. Never repeat what the user says back to them
2. If user asks vague questions like "kadom kursho" or "chi", ask clarifying questions
3. For course questions, provide specific information from these details:
   - New courses start: {course_start_date} (free lesson on 4th of same month)
   - Available courses: {formatted_courses}
   remember that explain users that for studing frontend mean js or python and c# they need to
     now Fundamentals thing in any programming language or they have to start from course programing from 0
   - Location: Rahimi Street, Dushanbe
4. If you can't answer, say "Sorry, I don't know. Please contact support using the help button."
5. Keep responses under 3 sentences unless more detail is needed
6. Never say "Бале" or just repeat the user's words
7. For unclear questions, respond with: "Could you please specify which course you're interested in?"
7. Always be polite and professional 
8. Keep responses under 800 characters
9. Answer in {language} language
5. For unrelated questions, suggest contacting support with operator 
6. If the user is inquiring about a specific course, provide details about that course
7. If the user is asking about course start dates, provide the date of the next course 
is 5th of next month and we have free lesson in 4th of next month
Current conversation history:
{conversation_history}

User's message: {message_text}


SOME MORE INFO IF u NEEDED:"Почему стоит выбрать курсы программирования от Softclub

    Reason 1
    Обучение проходит на английском, русском и таджикском языках.
    Reason 2
    В ходе курсов вы будете работать над реальными проектами.
    Reason 3
    По окончанию курса у вас будет сильное портфолио, с которого вы сможете найти работу.
    Reason 4
    Наши преподаватели — опытные практикующие специалисты.
    Reason 5
    Вы сами увидите прогресс — у нас 5 дней обучения в неделю каждую субботу экзамен.
    Reason 6
        Мы преподаем востребованные в Таджикистане и за рубежом языки программирования.
    Опыта преподавания
    4 лет
    Количество выпускников
    280+
    Трудоустроились в IT- компаниях
    68%
    Готовы нас рекомендовать
    98%

    Контакты
    info@softclub.tj
    +992 558 700 900
    улица Рахими 12, ориентир: Профсоюз
    "


"""
async def generate_ai_response(message_text: str, lang: str, user_id: int) -> str:
    """Generate AI response with conversation history"""
    conversation_history.add_message(user_id, "user", message_text)
    
    history = conversation_history.get_history(user_id)
    history_text = "\n".join(
        f"{msg['role']}: {msg['content']}" 
        for msg in history
    )
    
    course_start_date = get_course_start_date()
    
    registration_info = (
        f"For registration users need to push button {get_text('join_course', 'en')} or {get_text('join_course', 'tg')}\n"
        "and then they need to fill out the form with their name, phone number,\n"
        "After that, they will be registered for the course."
    )
    
    prompt = AI_PROMPT_TEMPLATE.format(
        message_text=message_text,
        language=lang,
        formatted_courses=courses_data,
        registration_info=registration_info,
        conversation_history=history_text,
        course_start_date=course_start_date  
    )
    
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.5,
            "top_p": 0.9,
            "top_k": 20,
            "max_output_tokens": 500,
        },
        safety_settings={
            "HARM_CATEGORY_HARASSMENT": "BLOCK_ONLY_HIGH",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_ONLY_HIGH",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_ONLY_HIGH",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_ONLY_HIGH",
        }
    )
    
    conversation_history.add_message(user_id, "assistant", response.text)
    
    return response.text