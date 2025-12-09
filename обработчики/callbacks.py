"""Упрощенные обработчики callback для работы с БД"""
import logging
from typing import Dict
from aiogram import Router, F, Bot
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from утилиты.database import db
from утилиты.keyboards import (
    build_main_keyboard,
    build_materials_level_keyboard,
    build_materials_list_keyboard,
    build_material_navigation_keyboard,
    build_material_info_keyboard,
    build_back_to_home_keyboard,
    build_stats_keyboard
)

router = Router()

# Временное хранилище для отслеживания видео-сообщений пользователей
# Формат: {user_id: video_message_id}
user_video_messages: Dict[int, int] = {}


async def delete_user_video_message(bot: Bot, user_id: int, chat_id: int) -> None:
    """Удаляет видео-сообщение пользователя, если оно есть"""
    if user_id in user_video_messages:
        video_message_id = user_video_messages[user_id]
        try:
            await bot.delete_message(chat_id=chat_id, message_id=video_message_id)
        except Exception as e:
            logging.debug(f"Could not delete video message {video_message_id}: {e}")
        finally:
            # Удаляем из хранилища
            del user_video_messages[user_id]


@router.callback_query(F.data == "home")
async def on_home(callback: CallbackQuery, bot: Bot) -> None:
    """Главное меню"""
    user_id = callback.from_user.id
    
    if not db.is_user_registered(user_id):
        await callback.answer("❌ Вы не зарегистрированы. Используйте /start", show_alert=True)
        return
    
    # Удаляем видео-сообщение при переходе на главную
    await delete_user_video_message(bot, user_id, callback.message.chat.id)
    
    db.update_user_activity(user_id)
    
    user = db.get_user(user_id)
    await callback.message.edit_text(
        f"👋 Добро пожаловать, <b>{user['name']} </b>!\n\n"
        "Выберите действие:",
        reply_markup=build_main_keyboard(user_id),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data == "materials_list")
async def on_materials_list(callback: CallbackQuery, bot: Bot) -> None:
    """Список материалов с выбором уровня"""
    user_id = callback.from_user.id
    
    if not db.is_user_registered(user_id):
        await callback.answer("❌ Вы не зарегистрированы", show_alert=True)
        return
    
    # Удаляем видео-сообщение при переходе к списку материалов
    await delete_user_video_message(bot, user_id, callback.message.chat.id)
    
    db.update_user_activity(user_id)
    
    text = "📚 <b>Выберите уровень сложности</b>\n\n"
    text += "🔰 Базовый - для начинающих\n"
    text += "⚡ Средний - для продолжающих\n"
    text += "🔥 Продвинутый - для опытных\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=build_materials_level_keyboard(),
                    parse_mode=ParseMode.HTML
                )
    await callback.answer()


@router.callback_query(F.data.startswith("materials_level:"))
async def on_materials_level(callback: CallbackQuery, bot: Bot) -> None:
    """Список материалов по уровню"""
    user_id = callback.from_user.id
    
    if not db.is_user_registered(user_id):
        await callback.answer("❌ Вы не зарегистрированы", show_alert=True)
        return
    
    # Удаляем видео-сообщение при переходе к списку материалов
    await delete_user_video_message(bot, user_id, callback.message.chat.id)
    
    db.update_user_activity(user_id)
    
    level = callback.data.split(":")[1]
    user_progress = db.get_user_progress(user_id)
    
    # Получаем материалы
    if level == "все":
        materials = db.get_all_materials()
        level_name = "Все материалы"
    else:
        materials = db.get_all_materials(level=level)
        level_names = {
            "базовый": "🔰 Базовый уровень",
            "средний": "⚡ Средний уровень",
            "продвинутый": "🔥 Продвинутый уровень"
        }
        level_name = level_names.get(level, level)
    
    if not materials:
        await callback.message.edit_text(
            f"📚 {level_name}\n\nМатериалы пока не добавлены.",
            reply_markup=build_back_to_home_keyboard()
        )
        await callback.answer()
        return
    
    text = f"📚 <b>{level_name}</b>\n\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=build_materials_list_keyboard(materials, user_progress),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data.startswith("material:"))
async def on_material(callback: CallbackQuery, bot: Bot) -> None:
    """Просмотр материала"""
    user_id = callback.from_user.id
    
    if not db.is_user_registered(user_id):
        await callback.answer("❌ Вы не зарегистрированы", show_alert=True)
        return
    
    # Удаляем предыдущее видео-сообщение при открытии нового материала
    await delete_user_video_message(bot, user_id, callback.message.chat.id)
    
    db.update_user_activity(user_id)
    
    material_id = int(callback.data.split(":")[1])
    await show_material_page(callback, bot, material_id, page_index=0)


@router.callback_query(F.data.startswith("material_page:"))
async def on_material_page(callback: CallbackQuery, bot: Bot) -> None:
    """Переход на страницу материала"""
    user_id = callback.from_user.id
    
    if not db.is_user_registered(user_id):
        await callback.answer("❌ Вы не зарегистрированы", show_alert=True)
        return
    
    parts = callback.data.split(":")
    material_id = int(parts[1])
    page_index = int(parts[2])
    
    # Если переходим на другую страницу (не первую), удаляем видео
    if page_index != 0:
        await delete_user_video_message(bot, user_id, callback.message.chat.id)
    
    await show_material_page(callback, bot, material_id, page_index)


async def show_material_page(callback: CallbackQuery, bot: Bot, material_id: int, page_index: int = 0) -> None:
    """Показывает страницу материала с форматированием"""
    from утилиты.text_formatter import format_text
    
    user_id = callback.from_user.id
    db.update_user_activity(user_id)
    
    material = db.get_material(material_id)
    
    if not material:
        await callback.answer("Материал не найден", show_alert=True)
        return
    
    # Отмечаем как изученный (только при первом просмотре)
    if page_index == 0:
        db.mark_material_studied(user_id, material_id)
    
    # Проверяем наличие теста
    questions = db.get_questions_for_material(material_id)
    has_test = len(questions) > 0
    
    # Показываем уровень сложности
    level_emoji = {
        "базовый": "🔰",
        "средний": "⚡",
        "продвинутый": "🔥"
    }
    level = material.get('level', 'базовый')
    emoji = level_emoji.get(level, "📖")
    
    # Проверяем наличие видео
    video_file_id = material.get('video_file_id')
    
    # Форматируем и разбиваем текст
    content_text = material['text_content']
    formatted_parts = format_text(content_text, max_length=3500)
    
    # Формируем заголовок
    header = f"{emoji} <b>{material['title']}</b>\n"
    header += f"📊 Уровень: <b>{level.capitalize()}</b>\n\n"
    
    # Формируем текст для текущей страницы
    if page_index < len(formatted_parts):
        page_text = formatted_parts[page_index]
        full_text = header + page_text
    else:
        full_text = header + formatted_parts[0] if formatted_parts else header
    
    # Добавляем информацию о странице, если несколько частей
    if len(formatted_parts) > 1:
        full_text += f"\n\n📄 <i>Страница {page_index + 1} из {len(formatted_parts)}</i>"
    
    # Создаем клавиатуру навигации
    is_last_page = (page_index == len(formatted_parts) - 1)
    keyboard = build_material_navigation_keyboard(
        material_id=material_id,
        has_test=has_test,
        page_index=page_index,
        total_pages=len(formatted_parts),
        is_last_page=is_last_page
    )
    
    # Добавляем сообщение об изучении только на первой странице
    if page_index == 0 and len(formatted_parts) == 1:
        full_text += "\n\n✅ Материал отмечен как изученным!"
    
    # Если есть видео на первой странице
    if page_index == 0 and video_file_id:
        try:
            # Удаляем предыдущее видео-сообщение, если оно есть
            await delete_user_video_message(bot, user_id, callback.message.chat.id)
            
            # Ограничение Telegram: caption максимум 1024 символа
            # Если текст короткий - используем подпись, если длинный - отдельные сообщения
            if len(full_text) <= 1024:
                # Короткий текст: видео с текстом в подписи и кнопками
                video_message = await callback.message.answer_video(
                    video=video_file_id,
                    caption=full_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
                # Сохраняем ID видео-сообщения для последующего удаления
                user_video_messages[user_id] = video_message.message_id
            else:
                # Длинный текст: отдельные сообщения
                # 1. Видео с кратким заголовком
                short_caption = header + "📹 <b>Видео к материалу</b>"
                if len(short_caption) > 1024:
                    short_caption = short_caption[:1021] + "..."
                
                video_message = await callback.message.answer_video(
                    video=video_file_id,
                    caption=short_caption,
                    parse_mode=ParseMode.HTML
                )
                # Сохраняем ID видео-сообщения
                user_video_messages[user_id] = video_message.message_id
                
                # 2. Текст материала с кнопками отдельным сообщением
                await callback.message.answer(
                    full_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            
            # Удаляем старое текстовое сообщение если возможно
            try:
                await callback.message.delete()
            except:
                pass
        except Exception as e:
            logging.warning(f"Error sending video: {e}")
            # Если не удалось отправить видео, отправляем обычный текст
            try:
                await callback.message.edit_text(
                    full_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e2:
                await callback.message.answer(
                    full_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
    else:
        # Обычное отображение текста без видео
        # Если переходим на другую страницу (не первую), удаляем видео
        if page_index != 0:
            await delete_user_video_message(bot, user_id, callback.message.chat.id)
        
        try:
            await callback.message.edit_text(
                full_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            # Если не удалось отредактировать (например, текст не изменился), отправляем новое сообщение
            logging.warning(f"Error editing message: {e}")
            await callback.message.answer(
                full_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
    
    await callback.answer()


@router.callback_query(F.data.startswith("material_info:"))
async def on_material_info(callback: CallbackQuery, bot: Bot) -> None:
    """Показывает информацию о материале"""
    user_id = callback.from_user.id
    
    # Удаляем видео-сообщение при переходе к информации о материале
    await delete_user_video_message(bot, user_id, callback.message.chat.id)
    
    material_id = int(callback.data.split(":")[1])
    material = db.get_material(material_id)
    
    if not material:
        await callback.answer("Материал не найден", show_alert=True)
        return
    
    questions = db.get_questions_for_material(material_id)
    level_emoji = {
        "базовый": "🔰",
        "средний": "⚡",
        "продвинутый": "🔥"
    }
    level = material.get('level', 'базовый')
    emoji = level_emoji.get(level, "📖")
    
    info_text = (
        f"{emoji} <b>{material['title']}</b>\n\n"
        f"📊 Уровень: <b>{level.capitalize()}</b>\n"
        f"📝 Вопросов в тесте: <b>{len(questions)}</b>\n"
        f"📄 Длина текста: <b>{len(material['text_content'])}</b> символов"
    )
    
    await callback.message.edit_text(
        info_text,
        reply_markup=build_material_info_keyboard(material_id),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data == "leaderboard")
async def on_leaderboard_callback(callback: CallbackQuery, bot: Bot) -> None:
    """Рейтинг через callback"""
    user_id = callback.from_user.id
    
    if not db.is_user_registered(user_id):
        await callback.answer("❌ Вы не зарегистрированы", show_alert=True)
        return
    
    # Удаляем видео-сообщение при переходе к рейтингу
    await delete_user_video_message(bot, user_id, callback.message.chat.id)
    
    db.update_user_activity(user_id)
    
    leaderboard = db.get_leaderboard(limit=10)
    user_rank = db.get_user_rank(user_id)
    
    if not leaderboard:
        await callback.message.edit_text(
            "📊 Рейтинг пока пуст. Станьте первым!",
            reply_markup=build_back_to_home_keyboard()
        )
        await callback.answer()
        return
    
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
    
    if user_rank and user_rank.get('rank'):
        rank = user_rank['rank']
        if rank > 10:
            text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📍 <b>Ваше место: #{rank}</b>\n"
            text += f"⭐ Баллов: {user_rank['total_score']:.1f}\n"
            text += f"📚 Материалов: {user_rank['materials_studied'] or 0}\n"
            text += f"📝 Тестов: {user_rank['tests_completed'] or 0}"
    
    text += "\n\n💪 Изучайте материалы и проходите тесты!"
    
    await callback.message.edit_text(
        text,
        reply_markup=build_back_to_home_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data == "my_stats")
async def on_my_stats(callback: CallbackQuery, bot: Bot) -> None:
    """Статистика пользователя"""
    user_id = callback.from_user.id
    
    if not db.is_user_registered(user_id):
        await callback.answer("❌ Вы не зарегистрированы", show_alert=True)
        return
    
    # Удаляем видео-сообщение при переходе к статистике
    await delete_user_video_message(bot, user_id, callback.message.chat.id)
    
    db.update_user_activity(user_id)
    
    user = db.get_user(user_id)
    user_progress = db.get_user_progress(user_id)
    user_rank = db.get_user_rank(user_id)
    
    all_materials = db.get_all_materials()
    total_materials = len(all_materials)
    studied_count = len(user_progress)
    percentage = (studied_count / total_materials * 100) if total_materials > 0 else 0
    
    text = f"📊 <b>Ваша статистика</b>\n\n"
    text += f"👤 Имя: <b>{user['name']}</b>\n"
    text += f"📅 Возраст: <b>{user['age']}</b>\n"
    text += f"🌍 {user['country']}, {user['city']}\n\n"
    text += f"📚 Изучено материалов: <b>{studied_count}/{total_materials}</b>\n"
    text += f"📈 Прогресс: <b>{percentage:.1f}%</b>\n"
    
    if user_rank and user_rank.get('rank'):
        text += f"🏆 Место в рейтинге: <b>#{user_rank['rank']}</b>\n"
        text += f"⭐ Баллов: <b>{user_rank['total_score']:.1f}</b>\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=build_stats_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


