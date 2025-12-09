"""Интеграция команды /ask c OpenRouter + память по пользователю"""
import logging
import os
from typing import Any, Dict, List

import requests
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from утилиты.database import db

router = Router()


def build_persona(user_alias: str) -> Dict[str, str]:
    """Базовая персона Specter."""
    return {
        "role": "system",
        "content": (
            "Ты — Specter, ИИ-наставник из BLACKCORE. Говори кратко, мрачно, по делу,"
            " только про компьютеры, Kali Linux, безопасность, анонимность и хакерство."
            " Без отклонений в другие темы. Поддерживай учеников, но будь требовательным."
            f" Пользователь: {user_alias}."
        ),
    }


def build_user_context(user_id: int) -> Dict[str, Any]:
    """Собирает профиль и прогресс пользователя для промпта."""
    snapshot = db.get_user_snapshot(user_id)
    user = snapshot.get("user") or {}

    profile_lines = []
    if user:
        profile_lines.append(
            f"Профиль: {user.get('name', 'неизвестно')} / {user_id}, "
            f"{user.get('age', 'N/A')} лет, {user.get('country', 'N/A')}, {user.get('city', 'N/A')}"
        )
    profile_lines.append(f"Изучено материалов: {snapshot.get('studied_count', 0)}")

    last_materials = snapshot.get("last_materials") or []
    if last_materials:
        titles = [f"{m['title']} ({m['level']})" for m in last_materials]
        profile_lines.append("Недавно изучал: " + "; ".join(titles))

    recent_tests = snapshot.get("recent_tests") or []
    if recent_tests:
        tests_text = []
        for t in recent_tests:
            tests_text.append(
                f"{t.get('title','Материал')} — {t['correct']}/{t['total']} ({t['percentage']:.1f}%)"
            )
        profile_lines.append("Последние тесты: " + "; ".join(tests_text))

    summary = db.get_ai_summary(user_id)
    if summary:
        profile_lines.append(f"Краткое summary: {summary}")

    return {
        "role": "system",
        "content": "Контекст ученика:\n" + "\n".join(profile_lines),
    }


def build_history(user_id: int, limit: int = 6) -> List[Dict[str, str]]:
    """Возвращает последние сообщения для подмешивания в контекст."""
    history = db.get_ai_history(user_id, limit=limit)
    messages: List[Dict[str, str]] = []
    for item in history:
        role = item.get("role", "user")
        content = item.get("content", "")
        if content:
            messages.append({"role": role, "content": content})
    return messages


def summarize_history(api_key: str, user_id: int, model: str = "openai/gpt-4o-mini") -> None:
    """Делает краткое summary по истории и сохраняет его в БД."""
    history = db.get_ai_history(user_id, limit=12)
    if len(history) < 8:
        return  # нет смысла сворачивать маленькую историю

    messages: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "Сделай краткое summary диалога в 3-5 тезисах."
                " Фокус: интересы, цели, проблемы пользователя и данные о прогрессе."
                " Формат — маркированные строки без лишнего."
            ),
        }
    ]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages}

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        summary = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if summary:
            db.upsert_ai_summary(user_id, summary)
    except Exception as exc:  # pylint: disable=broad-except
        logging.warning("Не удалось обновить summary: %s", exc)


@router.message(Command("ask"))
async def ask_llm(message: Message) -> None:
    """Отправляет вопрос пользователя в LLM и возвращает ответ с учётом контекста."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        await message.answer("⚠️ OPENROUTER_API_KEY не найден. Укажи его в .env")
        return

    # Убираем /ask из сообщения
    user_prompt = message.text.replace("/ask", "", 1).strip()
    if not user_prompt:
        await message.answer("Напиши вопрос после команды /ask")
        return

    user_alias = (
        message.from_user.username
        or message.from_user.full_name
        or "пользователь"
    )
    user_id = message.from_user.id

    # Сбор контекста
    messages: List[Dict[str, str]] = [build_persona(user_alias), build_user_context(user_id)]
    messages += build_history(user_id, limit=6)
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": messages,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        reply = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not reply:
            reply = "⚠️ Пустой ответ от модели."
    except Exception as exc:
        logging.exception("Ошибка при запросе к OpenRouter: %s", exc)
        reply = f"🚨 Ошибка при запросе к ИИ:\n{exc}"

    # Логируем историю
    try:
        db.log_ai_message(user_id, "user", user_prompt)
        db.log_ai_message(user_id, "assistant", reply)
        summarize_history(api_key, user_id)
    except Exception as exc:
        logging.warning("Не удалось сохранить историю ИИ: %s", exc)

    await message.answer(f"💬 Ответ Specter:\n{reply}", reply_markup=None)
