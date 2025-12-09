"""Упрощенные обработчики тестов для работы с БД"""
import logging
from typing import List, Dict

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from утилиты.database import db

router = Router()

# Временное хранилище активных тестов
user_active_tests: Dict[int, Dict] = {}


def create_answer_keyboard(question_index: int, answers: List[Dict], user_id: int, material_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру с вариантами ответов
    
    Args:
        question_index: Индекс вопроса
        answers: Список ответов
        user_id: ID пользователя
        material_id: ID материала
    """
    buttons = []
    
    for i, answer in enumerate(answers):
        answer_text = answer['answer_text']
        button_text = answer_text[:50] + "..." if len(answer_text) > 50 else answer_text
        # Формат: test_answer:user_id:material_id:question_index:answer_index
        buttons.append([
            InlineKeyboardButton(
                text=f"{chr(65 + i)}. {button_text}",
                callback_data=f"test_answer:{user_id}:{material_id}:{question_index}:{i}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(text="❌ Отменить тест", callback_data=f"test_cancel:{user_id}:{material_id}")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("test_start:"))
async def on_test_start(callback: CallbackQuery) -> None:
    """Начало теста"""
    try:
        user_id = callback.from_user.id
        
        if not db.is_user_registered(user_id):
            await callback.answer("❌ Вы не зарегистрированы", show_alert=True)
            return
        
        db.update_user_activity(user_id)
        
        material_id = int(callback.data.split(":")[1])
        
        # Получаем вопросы для материала
        questions = db.get_questions_for_material(material_id)
        
        if not questions:
            await callback.answer("Тест для этого материала не найден", show_alert=True)
            return
        
        # Сохраняем активный тест
        user_active_tests[user_id] = {
            "material_id": material_id,
            "questions": questions,
            "current_question": 0,
            "answers": []
        }
        
        # Показываем первый вопрос
        await show_question(callback, user_id, 0)
        
    except Exception as e:
        logging.exception(f"Error starting test: {e}")
        await callback.answer("Ошибка при запуске теста", show_alert=True)


async def show_question(callback: CallbackQuery, user_id: int, question_index: int) -> None:
    """Показывает вопрос теста"""
    if user_id not in user_active_tests:
        await callback.answer("Тест не найден", show_alert=True)
        return
    
    test = user_active_tests[user_id]
    questions = test["questions"]
    
    if question_index >= len(questions):
        # Все вопросы отвечены - завершаем тест
        await finish_test(callback, user_id)
        return
    
    question = questions[question_index]
    material_id = test["material_id"]
    answers = question['answers']
    
    # Формируем текст вопроса
    question_text = (
        f"📝 <b>Вопрос {question_index + 1} из {len(questions)}</b>\n\n"
        f"{question['question_text']}\n\n"
        f"Выберите правильный ответ:"
    )
    
    # Создаем клавиатуру (передаем user_id и material_id отдельно)
    kb = create_answer_keyboard(question_index, answers, user_id, material_id)
    
    try:
        await callback.message.edit_text(question_text, reply_markup=kb, parse_mode=ParseMode.HTML)
        await callback.answer()
    except Exception as e:
        logging.warning(f"Error editing message: {e}")
        await callback.message.answer(question_text, reply_markup=kb, parse_mode=ParseMode.HTML)
        await callback.answer()


@router.callback_query(F.data.startswith("test_answer:"))
async def on_test_answer(callback: CallbackQuery) -> None:
    """Обработка ответа на вопрос"""
    try:
        # Формат: test_answer:user_id:material_id:question_index:answer_index
        # Разбиваем правильно, учитывая что test_id содержит двоеточие
        data = callback.data[len("test_answer:"):]  # Убираем префикс
        parts = data.split(":")
        
        if len(parts) < 4:
            await callback.answer("Неверный формат", show_alert=False)
            return
        
        # Формат: user_id:material_id:question_index:answer_index
        user_id_from_data = int(parts[0])
        material_id_from_data = int(parts[1])
        question_index = int(parts[2])
        answer_index = int(parts[3])
        
        user_id = callback.from_user.id
        
        # Проверяем, что user_id совпадает
        if user_id != user_id_from_data:
            await callback.answer("Неверный пользователь", show_alert=True)
            return
        
        if user_id not in user_active_tests:
            await callback.answer("Тест не найден", show_alert=True)
            return
        
        test = user_active_tests[user_id]
        
        # Проверяем, что material_id совпадает
        if test["material_id"] != material_id_from_data:
            await callback.answer("Неверный тест", show_alert=True)
            return
        
        if test["current_question"] != question_index:
            await callback.answer("Вопрос уже отвечен", show_alert=False)
            return
        
        # Сохраняем ответ
        question = test["questions"][question_index]
        answers = question['answers']
        selected_answer = answers[answer_index]
        
        test["answers"].append(answer_index)
        test["current_question"] += 1
        
        # Показываем результат
        is_correct = selected_answer['is_correct']
        if is_correct:
            await callback.answer("✅ Правильно!", show_alert=False)
        else:
            # Находим правильный ответ
            correct_answer = next((a for a in answers if a['is_correct']), None)
            correct_text = correct_answer['answer_text'] if correct_answer else "Не указано"
            await callback.answer(f"❌ Неправильно. Правильный ответ: {correct_text[:50]}", show_alert=True)
        
        # Показываем следующий вопрос
        await show_question(callback, user_id, test["current_question"])
        
    except Exception as e:
        logging.exception(f"Error processing answer: {e}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("test_cancel:"))
async def on_test_cancel(callback: CallbackQuery) -> None:
    """Отмена теста"""
    try:
        # Формат: test_cancel:user_id:material_id
        data = callback.data[len("test_cancel:"):]
        parts = data.split(":")
        
        if len(parts) < 2:
            await callback.answer("Ошибка", show_alert=True)
            return
        
        user_id_from_data = int(parts[0])
        material_id_from_data = int(parts[1])
        user_id = callback.from_user.id
        
        if user_id != user_id_from_data:
            await callback.answer("Ошибка", show_alert=True)
            return
        
        if user_id in user_active_tests:
            if user_active_tests[user_id]["material_id"] == material_id_from_data:
                del user_active_tests[user_id]
        
        await callback.message.edit_text(
            "❌ Тест отменён.\n\nВы можете начать его заново в любое время.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главная", callback_data="home")]
            ])
        )
        await callback.answer("Тест отменён")
        
    except Exception as e:
        logging.exception(f"Error canceling test: {e}")
        await callback.answer("Ошибка", show_alert=True)


async def finish_test(callback: CallbackQuery, user_id: int) -> None:
    """Завершение теста и показ результатов"""
    if user_id not in user_active_tests:
        await callback.answer("Тест не найден", show_alert=True)
        return
    
    test = user_active_tests[user_id]
    material_id = test["material_id"]
    questions = test["questions"]
    answers = test["answers"]
    
    # Подсчитываем результаты
    correct = 0
    total = len(questions)
    
    for i, question in enumerate(questions):
        if i < len(answers):
            answer_index = answers[i]
            selected_answer = question['answers'][answer_index]
            if selected_answer['is_correct']:
                correct += 1
    
    percentage = (correct / total * 100) if total > 0 else 0.0
    passed = percentage >= 60.0
    
    # Сохраняем результат
    db.save_test_result(user_id, material_id, correct, total, percentage)
    db.update_user_activity(user_id)
    
    # Формируем текст результата
    if percentage >= 80:
        emoji = "🎉"
        message = "Отлично! Вы хорошо усвоили материал!"
    elif percentage >= 60:
        emoji = "👍"
        message = "Хорошо! Но есть что повторить."
    else:
        emoji = "📚"
        message = "Рекомендуется перечитать материал."
    
    result_text = (
        f"{emoji} <b>Результаты теста</b>\n\n"
        f"✅ Правильных ответов: <b>{correct}/{total}</b>\n"
        f"📊 Оценка: <b>{percentage:.1f}%</b>\n\n"
        f"{message}"
    )
    
    if passed:
        result_text += "\n\n✅ <b>Материал отмечен как изученный!</b>"
    else:
        result_text += "\n\n💡 <b>Изучите материал ещё раз и попробуйте пройти тест снова.</b>"
    
    # Клавиатура
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Пройти заново", callback_data=f"test_start:{material_id}")],
        [InlineKeyboardButton(text="📚 К списку материалов", callback_data="materials_list")],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="home")]
    ])
    
    # Удаляем активный тест
    del user_active_tests[user_id]
    
    # Показываем результаты
    try:
        await callback.message.edit_text(result_text, reply_markup=kb, parse_mode=ParseMode.HTML)
        await callback.answer()
    except Exception as e:
        logging.warning(f"Error editing message: {e}")
        await callback.message.answer(result_text, reply_markup=kb, parse_mode=ParseMode.HTML)
        await callback.answer()
