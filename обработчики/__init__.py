"""Упрощенные обработчики бота"""
from aiogram import Router

from .commands import router as commands_router
from .callbacks import router as callbacks_router
from .tests import router as tests_router
from .admin import router as admin_router
from .ai import router as ai_router

# Создаём главный роутер
router = Router()

# Включаем все под-роутеры
router.include_router(commands_router)
router.include_router(callbacks_router)
router.include_router(tests_router)
router.include_router(admin_router)  # Административные команды
router.include_router(ai_router)  # Команда /ask с LLM

__all__ = ["router"]

