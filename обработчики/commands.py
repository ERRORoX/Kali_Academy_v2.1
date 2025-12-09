"""Упрощенные обработчики команд"""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from утилиты.database import db
from утилиты.keyboards import build_main_keyboard

router = Router()


class RegistrationStates(StatesGroup):
    """Состояния регистрации"""
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_country = State()
    waiting_for_city = State()


@router.message(CommandStart())
async def on_start(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start - начало регистрации"""
    user_id = message.from_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    if db.is_user_registered(user_id):
        # Пользователь уже зарегистрирован - показываем главное меню
        user = db.get_user(user_id)
        await message.answer(
            f"👋 Добро пожаловать, <b>{user['name']}</b>!\n\n"
            "Выберите действие:",
            reply_markup=build_main_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )
        return
    
    # Начинаем регистрацию
    await state.set_state(RegistrationStates.waiting_for_name)
    await message.answer(
        "👋 <b>Добро пожаловать в Kali Linux Academy!</b>\n\n"
        "Для начала работы нужно пройти регистрацию.\n\n"
        "📝 <b>Введите ваше имя:</b>",
        parse_mode=ParseMode.HTML
    )


@router.message(RegistrationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext) -> None:
    """Обработка имени"""
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя слишком короткое. Введите имя (минимум 2 символа):")
        return
    
    await state.update_data(name=name)
    await state.set_state(RegistrationStates.waiting_for_age)
    await message.answer("📅 <b>Введите ваш возраст:</b>", parse_mode=ParseMode.HTML)


@router.message(RegistrationStates.waiting_for_age)
async def process_age(message: Message, state: FSMContext) -> None:
    """Обработка возраста"""
    try:
        age = int(message.text.strip())
        if age < 1 or age > 150:
            await message.answer("❌ Возраст должен быть от 1 до 150. Введите корректный возраст:")
            return
    except ValueError:
        await message.answer("❌ Введите число (ваш возраст):")
        return
    
    await state.update_data(age=age)
    await state.set_state(RegistrationStates.waiting_for_country)
    await message.answer("🌍 <b>Введите вашу страну:</b>", parse_mode=ParseMode.HTML)


@router.message(RegistrationStates.waiting_for_country)
async def process_country(message: Message, state: FSMContext) -> None:
    """Обработка страны"""
    country = message.text.strip()
    if len(country) < 2:
        await message.answer("❌ Название страны слишком короткое. Введите страну:")
        return
    
    await state.update_data(country=country)
    await state.set_state(RegistrationStates.waiting_for_city)
    await message.answer("🏙️ <b>Введите ваш город:</b>", parse_mode=ParseMode.HTML)


@router.message(RegistrationStates.waiting_for_city)
async def process_city(message: Message, state: FSMContext) -> None:
    """Обработка города и завершение регистрации"""
    city = message.text.strip()
    if len(city) < 2:
        await message.answer("❌ Название города слишком короткое. Введите город:")
        return
    
    data = await state.get_data()
    
    # Регистрируем пользователя
    db.register_user(
        user_id=message.from_user.id,
        name=data['name'],
        age=data['age'],
        country=data['country'],
        city=city
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>Регистрация завершена!</b>\n\n"
        f"👤 Имя: <b>{data['name']}</b>\n"
        f"📅 Возраст: <b>{data['age']}</b>\n"
        f"🌍 Страна: <b>{data['country']}</b>\n"
        f"🏙️ Город: <b>{city}</b>\n\n"
        f"Теперь вы можете начать изучение материалов!",
        reply_markup=build_main_keyboard(message.from_user.id),
        parse_mode=ParseMode.HTML
    )


@router.message(Command("leaderboard"))
async def on_leaderboard(message: Message) -> None:
    """Показывает рейтинг пользователей"""
    user_id = message.from_user.id
    
    if not db.is_user_registered(user_id):
        await message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return
    
    db.update_user_activity(user_id)
    
    # Получаем рейтинг
    leaderboard = db.get_leaderboard(limit=10)
    user_rank = db.get_user_rank(user_id)
    
    if not leaderboard:
        await message.answer("📊 Рейтинг пока пуст. Станьте первым!")
        return
    
    # Формируем текст рейтинга
    text = "🏆 <b>ТОП-10 ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for entry in leaderboard:
        rank = entry['rank']
        medal = medals[rank - 1] if rank <= 3 else "  "
        name = entry['name']
        score = entry['total_score']
        materials = entry['materials_studied'] or 0
        tests = entry['tests_completed'] or 0
        country = entry.get('country', 'Неизвестно') or 'Неизвестно'
        city = entry.get('city', 'Неизвестно') or 'Неизвестно'
        age = entry.get('age', 'Неизвестно') or 'Неизвестно'

        text += (
            f"{medal} <b>#{rank}</b> {name}\n"
            f"   🌍 {country}, {city} | 👤 {age} лет\n"
            f"   ⭐ Баллов: {score:.1f} | "
            f"📚 Материалов: {materials} | "
            f"📝 Тестов: {tests}\n\n"
        )
    
    # Показываем место пользователя
    if user_rank and user_rank.get('rank'):
        rank = user_rank['rank']
        if rank > 10:
            text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📍 <b>Ваше место: #{rank}</b>\n"
            text += f"⭐ Баллов: {user_rank['total_score']:.1f}\n"
            text += f"📚 Материалов: {user_rank['materials_studied'] or 0}\n"
            text += f"📝 Тестов: {user_rank['tests_completed'] or 0}"
    
    text += "\n\n💪 Изучайте материалы и проходите тесты, чтобы подняться выше!"
    
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главная", callback_data="home")]
        ]),
        parse_mode=ParseMode.HTML
    )


