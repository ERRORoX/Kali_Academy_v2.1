"""
Административные команды для управления материалами и тестами

Позволяют добавлять, удалять и редактировать материалы прямо из Telegram
без знания программирования.
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Video
from aiogram.enums import ParseMode

from утилиты.database import db
from утилиты.auth import is_admin

router = Router()


class AddMaterialStates(StatesGroup):
    """Состояния для добавления материала"""
    waiting_for_title = State() # ожидание названия материала
    waiting_for_text = State() # ожидание текста материала
    waiting_for_level = State() # ожидание уровня сложности материала
    waiting_for_questions = State()
    waiting_for_question_text = State()
    waiting_for_answers = State()
    waiting_for_correct = State()


class EditMaterialStates(StatesGroup):
    """Состояния для редактирования материала"""
    waiting_for_material_selection = State()
    waiting_for_edit_choice = State()
    waiting_for_new_title = State()
    waiting_for_additional_text = State()
    waiting_for_video = State()


@router.message(Command("add_material"))
async def cmd_add_material(message: Message, state: FSMContext) -> None:
    """Начало добавления материала"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    await state.set_state(AddMaterialStates.waiting_for_title)
    await message.answer(
        "➕ <b>Добавление нового материала</b>\n\n"
        "📝 <b>Шаг 1 из 3:</b> Введите название материала:",
        parse_mode=ParseMode.HTML
    )


@router.message(AddMaterialStates.waiting_for_title)
async def process_title(message: Message, state: FSMContext) -> None:
    """Обработка названия"""
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("❌ Название слишком короткое (минимум 3 символа). Введите снова:")
        return
    
    await state.update_data(title=title)
    await state.set_state(AddMaterialStates.waiting_for_text)
    await message.answer(
        f"✅ Название сохранено: <b>{title}</b>\n\n"
        "📄 <b>Шаг 2 из 3:</b> Введите текст материала.\n"
        "Можно вводить несколько сообщений. Когда закончите, отправьте команду /done",
        parse_mode=ParseMode.HTML
    )


@router.message(AddMaterialStates.waiting_for_text)
async def process_text(message: Message, state: FSMContext) -> None:
    """Обработка текста материала"""
    if message.text and message.text.strip() == "/done":
        data = await state.get_data()
        if 'text_content' not in data or not data['text_content']:
            await message.answer("❌ Текст материала не может быть пустым. Введите текст:")
            return
        
        await state.set_state(AddMaterialStates.waiting_for_level)
        await message.answer(
            "✅ Текст сохранен!\n\n"
            "🎯 <b>Шаг 3 из 3:</b> Выберите уровень сложности:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔰 Базовый", callback_data="level:базовый")],
                [InlineKeyboardButton(text="⚡ Средний", callback_data="level:средний")],
                [InlineKeyboardButton(text="🔥 Продвинутый", callback_data="level:продвинутый")]
            ]),
            parse_mode=ParseMode.HTML
        )
        return
    
    # Добавляем текст к существующему
    data = await state.get_data()
    current_text = data.get('text_content', '')
    new_text = message.text or ""
    
    if current_text:
        text_content = current_text + "\n" + new_text
    else:
        text_content = new_text
    
    await state.update_data(text_content=text_content)
    await message.answer(
        f"✅ Текст добавлен ({len(text_content)} символов)\n"
        "Продолжайте вводить или отправьте /done для завершения"
    )


@router.callback_query(F.data.startswith("level:"))
async def process_level(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора уровня"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    level = callback.data.split(":")[1]
    data = await state.get_data()
    
    # Добавляем материал в БД
    material_id = db.add_material(
        title=data['title'],
        text_content=data['text_content'],
        level=level
    )
    
    await state.update_data(material_id=material_id, level=level)
    await state.set_state(AddMaterialStates.waiting_for_questions)
    
    level_emoji = {"базовый": "🔰", "средний": "⚡", "продвинутый": "🔥"}
    
    await callback.message.edit_text(
        f"✅ <b>Материал добавлен!</b>\n\n"
        f"📝 Название: <b>{data['title']}</b>\n"
        f"{level_emoji.get(level, '📖')} Уровень: <b>{level}</b>\n"
        f"📄 Текст: {len(data['text_content'])} символов\n\n"
        f"Теперь можно добавить вопросы к тесту.\n\n"
        f"❓ Введите первый вопрос или отправьте /skip чтобы пропустить:",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.message(AddMaterialStates.waiting_for_questions)
async def process_question_start(message: Message, state: FSMContext) -> None:
    """Начало добавления вопроса"""
    if message.text and message.text.strip() == "/skip":
        data = await state.get_data()
        await state.clear()
        await message.answer(
            f"✅ <b>Материал создан!</b>\n\n"
            f"📝 ID: <b>{data['material_id']}</b>\n"
            f"📚 Название: <b>{data['title']}</b>\n\n"
            f"Вопросы можно добавить позже командой /add_question",
            parse_mode=ParseMode.HTML
        )
        return
    
    question_text = message.text.strip()
    if len(question_text) < 5:
        await message.answer("❌ Вопрос слишком короткий. Введите вопрос:")
        return
    
    await state.update_data(current_question=question_text)
    await state.set_state(AddMaterialStates.waiting_for_answers)
    await message.answer(
        f"✅ Вопрос сохранен: <b>{question_text}</b>\n\n"
        f"📋 Теперь введите варианты ответов через запятую:\n"
        f"Например: <code>Правильный ответ,Неправильный 1,Неправильный 2</code>",
        parse_mode=ParseMode.HTML
    )


@router.message(AddMaterialStates.waiting_for_answers)
async def process_answers(message: Message, state: FSMContext) -> None:
    """Обработка вариантов ответов"""
    answers_input = message.text.strip()
    answer_list = [a.strip() for a in answers_input.split(",") if a.strip()]
    
    if len(answer_list) < 2:
        await message.answer("❌ Нужно минимум 2 варианта ответа. Введите снова через запятую:")
        return
    
    await state.update_data(current_answers=answer_list)
    await state.set_state(AddMaterialStates.waiting_for_correct)
    
    # Показываем варианты с номерами
    answers_text = "\n".join([f"{i+1}. {ans}" for i, ans in enumerate(answer_list)])
    await message.answer(
        f"✅ Варианты ответов сохранены:\n\n{answers_text}\n\n"
        f"✅ Введите номер правильного ответа (1-{len(answer_list)}):",
        parse_mode=ParseMode.HTML
    )


@router.message(AddMaterialStates.waiting_for_correct)
async def process_correct_answer(message: Message, state: FSMContext) -> None:
    """Обработка правильного ответа"""
    try:
        correct_num = int(message.text.strip())
        data = await state.get_data()
        answer_list = data['current_answers']
        
        if correct_num < 1 or correct_num > len(answer_list):
            await message.answer(f"❌ Неверный номер. Введите число от 1 до {len(answer_list)}:")
            return
        
        correct_index = correct_num - 1  # Преобразуем в 0-based
        
        # Добавляем вопрос в БД
        material_id = data['material_id']
        question_id = db.add_question(material_id, data['current_question'])
        
        # Добавляем ответы
        for i, answer_text in enumerate(answer_list):
            is_correct = (i == correct_index)
            db.add_answer(question_id, answer_text, is_correct)
        
        # Сохраняем счетчик вопросов
        questions_count = data.get('questions_count', 0) + 1
        await state.update_data(questions_count=questions_count)
        
        await message.answer(
            f"✅ Вопрос {questions_count} добавлен!\n\n"
            f"❓ Введите следующий вопрос или отправьте /done для завершения:",
            parse_mode=ParseMode.HTML
        )
        
        # Возвращаемся к состоянию добавления вопросов
        await state.set_state(AddMaterialStates.waiting_for_questions)
        
    except ValueError:
        await message.answer("❌ Введите число (номер правильного ответа):")


@router.message(Command("done"))
async def cmd_done(message: Message, state: FSMContext) -> None:
    """Завершение добавления вопросов"""
    current_state = await state.get_state()
    
    if current_state == AddMaterialStates.waiting_for_questions:
        data = await state.get_data()
        questions_count = data.get('questions_count', 0)
        await state.clear()
        
        await message.answer(
            f"✅ <b>Готово!</b>\n\n"
            f"📝 Материал: <b>{data['title']}</b>\n"
            f"❓ Вопросов добавлено: <b>{questions_count}</b>\n\n"
            f"Материал готов к использованию!",
            parse_mode=ParseMode.HTML
        )


@router.message(Command("edit_material"))
async def cmd_edit_material(message: Message, state: FSMContext) -> None:
    """Редактирование материала"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    materials = db.get_all_materials()
    
    if not materials:
        await message.answer("📚 Материалы не найдены")
        return
    
    text = "✏️ <b>Выберите материал для редактирования:</b>\n\n"
    buttons = []
    
    for material in materials[:15]:
        level_emoji = {"базовый": "🔰", "средний": "⚡", "продвинутый": "🔥"}
        emoji = level_emoji.get(material.get('level', 'базовый'), "📖")
        buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} {material['title']}",
                callback_data=f"edit_mat:{material['id']}"
            )
        ])
    
    await state.set_state(EditMaterialStates.waiting_for_material_selection)
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("edit_mat:"), EditMaterialStates.waiting_for_material_selection)
async def on_edit_material_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора материала для редактирования"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    material_id = int(callback.data.split(":")[1])
    material = db.get_material(material_id)
    
    if not material:
        await callback.answer("Материал не найден", show_alert=True)
        return
    
    await state.update_data(material_id=material_id)
    await state.set_state(EditMaterialStates.waiting_for_edit_choice)
    
    has_video = bool(material.get('video_file_id'))
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование материала</b>\n\n"
        f"📝 <b>{material['title']}</b>\n\n"
        f"Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Изменить название", callback_data="edit_action:title")],
            [InlineKeyboardButton(text="➕ Дополнить текст", callback_data="edit_action:append")],
            [InlineKeyboardButton(text="📹 Добавить/Изменить видео", callback_data="edit_action:video")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_action:cancel")]
        ]),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_action:"), EditMaterialStates.waiting_for_edit_choice)
async def on_edit_action(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора действия редактирования"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    action = callback.data.split(":")[1]
    
    if action == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Редактирование отменено")
        await callback.answer()
        return
    
    data = await state.get_data()
    material_id = data['material_id']
    
    if action == "title":
        await state.set_state(EditMaterialStates.waiting_for_new_title)
        await callback.message.edit_text(
            "📝 Введите новое название материала:",
            parse_mode=ParseMode.HTML
        )
    elif action == "append":
        await state.set_state(EditMaterialStates.waiting_for_additional_text)
        await callback.message.edit_text(
            "➕ Введите текст, который нужно добавить к материалу:\n\n"
            "(Текст будет добавлен в конец существующего материала)",
            parse_mode=ParseMode.HTML
        )
    elif action == "video":
        await state.set_state(EditMaterialStates.waiting_for_video)
        await callback.message.edit_text(
            "📹 Отправьте видео для материала:\n\n"
            "(Можно отправить видео файл или видео сообщение)",
            parse_mode=ParseMode.HTML
        )
    
    await callback.answer()


@router.message(EditMaterialStates.waiting_for_new_title)
async def process_new_title(message: Message, state: FSMContext) -> None:
    """Обработка нового названия"""
    new_title = message.text.strip()
    if len(new_title) < 3:
        await message.answer("❌ Название слишком короткое. Введите снова:")
        return
    
    data = await state.get_data()
    material_id = data['material_id']
    
    if db.update_material(material_id, title=new_title):
        await state.clear()
        await message.answer(
            f"✅ Название обновлено: <b>{new_title}</b>",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer("❌ Ошибка при обновлении названия")


@router.message(EditMaterialStates.waiting_for_additional_text)
async def process_additional_text(message: Message, state: FSMContext) -> None:
    """Обработка дополнительного текста"""
    additional_text = message.text.strip()
    if not additional_text:
        await message.answer("❌ Текст не может быть пустым. Введите текст:")
        return
    
    data = await state.get_data()
    material_id = data['material_id']
    
    if db.append_to_material(material_id, additional_text):
        await state.clear()
        await message.answer(
            f"✅ Текст добавлен к материалу!\n\n"
            f"Добавлено: {len(additional_text)} символов",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer("❌ Ошибка при добавлении текста")


@router.message(EditMaterialStates.waiting_for_video, F.video)
async def process_video(message: Message, state: FSMContext) -> None:
    """Обработка видео"""
    video_file_id = message.video.file_id
    
    data = await state.get_data()
    material_id = data['material_id']
    
    if db.update_material(material_id, video_file_id=video_file_id):
        await state.clear()
        await message.answer(
            f"✅ Видео добавлено к материалу!",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer("❌ Ошибка при добавлении видео")


@router.message(EditMaterialStates.waiting_for_video)
async def process_video_error(message: Message, state: FSMContext) -> None:
    """Обработка ошибки при отправке видео"""
    await message.answer("❌ Пожалуйста, отправьте видео файл")


@router.message(Command("list_materials"))
async def cmd_list_materials(message: Message) -> None:
    """Список всех материалов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    materials = db.get_all_materials()
    
    if not materials:
        await message.answer("📚 Материалы не найдены")
        return
    
    text = f"📚 <b>Всего материалов: {len(materials)}</b>\n\n"
    
    for material in materials[:20]:  # Показываем первые 20
        questions = db.get_questions_for_material(material['id'])
        level_emoji = {"базовый": "🔰", "средний": "⚡", "продвинутый": "🔥"}
        emoji = level_emoji.get(material.get('level', 'базовый'), "📖")
        has_video = "📹" if material.get('video_file_id') else "  "
        
        text += (
            f"{emoji} {has_video} <b>ID {material['id']}:</b> {material['title']}\n"
            f"   📊 Уровень: {material.get('level', 'не указан')}\n"
            f"   ❓ Вопросов: {len(questions)}\n\n"
        )
    
    if len(materials) > 20:
        text += f"\n... и ещё {len(materials) - 20} материалов"
    
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(Command("delete_material"))
async def cmd_delete_material(message: Message, state: FSMContext) -> None:
    """Удаление материала"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    # Показываем список материалов для выбора
    materials = db.get_all_materials()
    
    if not materials:
        await message.answer("📚 Материалы не найдены")
        return
    
    text = "🗑️ <b>Выберите материал для удаления:</b>\n\n"
    buttons = []
    
    for material in materials[:15]:  # Показываем первые 15
        level_emoji = {"базовый": "🔰", "средний": "⚡", "продвинутый": "🔥"}
        emoji = level_emoji.get(material.get('level', 'базовый'), "📖")
        buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} {material['title']}",
                callback_data=f"delete_mat:{material['id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")])
    
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("delete_mat:"))
async def confirm_delete(callback: CallbackQuery) -> None:
    """Подтверждение удаления"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    material_id = int(callback.data.split(":")[1])
    material = db.get_material(material_id)
    
    if not material:
        await callback.answer("Материал не найден", show_alert=True)
        return
    
    # Удаляем
    if db.delete_material(material_id):
        await callback.message.edit_text(
            f"✅ <b>Материал удален!</b>\n\n"
            f"📝 {material['title']}\n"
            f"Все вопросы и ответы также удалены.",
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.message.edit_text("❌ Ошибка при удалении")
    
    await callback.answer()


@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery) -> None:
    """Отмена удаления"""
    await callback.message.edit_text("❌ Удаление отменено")
    await callback.answer()


@router.message(Command("add_question"))
async def cmd_add_question(message: Message, state: FSMContext) -> None:
    """Добавление вопроса к существующему материалу"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    materials = db.get_all_materials()
    
    if not materials:
        await message.answer("📚 Сначала создайте материал командой /add_material")
        return
    
    text = "❓ <b>Выберите материал для добавления вопроса:</b>\n\n"
    buttons = []
    
    for material in materials[:15]:
        level_emoji = {"базовый": "🔰", "средний": "⚡", "продвинутый": "🔥"}
        emoji = level_emoji.get(material.get('level', 'базовый'), "📖")
        buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} {material['title']}",
                callback_data=f"add_q_to:{material['id']}"
            )
        ])
    
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("add_q_to:"))
async def start_add_question(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало добавления вопроса к материалу"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    material_id = int(callback.data.split(":")[1])
    material = db.get_material(material_id)
    
    if not material:
        await callback.answer("Материал не найден", show_alert=True)
        return
    
    await state.update_data(material_id=material_id)
    await state.set_state(AddMaterialStates.waiting_for_question_text)
    
    await callback.message.edit_text(
        f"✅ Материал: <b>{material['title']}</b>\n\n"
        f"❓ Введите текст вопроса:",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.message(AddMaterialStates.waiting_for_question_text)
async def process_question_text(message: Message, state: FSMContext) -> None:
    """Обработка текста вопроса"""
    question_text = message.text.strip()
    if len(question_text) < 5:
        await message.answer("❌ Вопрос слишком короткий. Введите вопрос:")
        return
    
    await state.update_data(current_question=question_text)
    await state.set_state(AddMaterialStates.waiting_for_answers)
    await message.answer(
        f"✅ Вопрос сохранен: <b>{question_text}</b>\n\n"
        f"📋 Введите варианты ответов через запятую:\n"
        f"Например: <code>Правильный ответ,Неправильный 1,Неправильный 2</code>",
        parse_mode=ParseMode.HTML
    )


@router.message(Command("help_admin"))
async def cmd_help_admin(message: Message) -> None:
    """Справка по административным командам"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    help_text = (
        "🔧 <b>АДМИНИСТРАТИВНЫЕ КОМАНДЫ</b>\n\n"
        "➕ <b>/add_material</b> - Добавить новый материал с тестом\n"
        "   Просто следуйте инструкциям бота!\n\n"
        "✏️ <b>/edit_material</b> - Редактировать материал\n"
        "   - Изменить название\n"
        "   - Дополнить текст\n"
        "   - Добавить/изменить видео\n\n"
        "❓ <b>/add_question</b> - Добавить вопрос к существующему материалу\n\n"
        "📋 <b>/list_materials</b> - Показать список всех материалов\n\n"
        "🗑️ <b>/delete_material</b> - Удалить материал\n\n"
        "✅ <b>/done</b> - Завершить добавление вопросов\n\n"
        "💡 <b>Совет:</b> Используйте /add_material для создания материала с тестом за один раз!"
    )
    
    await message.answer(help_text, parse_mode=ParseMode.HTML)
