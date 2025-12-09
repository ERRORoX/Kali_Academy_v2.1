"""Упрощенные утилиты для бота"""
from .database import db
from .auth import is_admin
from .keyboards import (
    build_main_keyboard,
    build_materials_level_keyboard,
    build_materials_list_keyboard,
    build_material_navigation_keyboard,
    build_material_info_keyboard,
    build_back_to_home_keyboard,
    build_stats_keyboard
)

__all__ = [
    "db",
    "is_admin",
    "build_main_keyboard",
    "build_materials_level_keyboard",
    "build_materials_list_keyboard",
    "build_material_navigation_keyboard",
    "build_material_info_keyboard",
    "build_back_to_home_keyboard",
    "build_stats_keyboard"
]
