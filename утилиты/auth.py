"""
Модуль для проверки прав доступа

Принцип разделения ответственности:
- Только проверка прав доступа
- Не содержит бизнес-логики обработчиков
"""
from pathlib import Path
import os
from dotenv import load_dotenv


def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором
    
    Принцип работы:
    1. Читает список администраторов из переменной окружения ADMIN_IDS
    2. Если список не указан, разрешает всем (для тестирования)
    3. В продакшене рекомендуется указать ADMIN_IDS в .env
    
    Args:
        user_id: ID пользователя Telegram
    
    Returns:
        True если пользователь администратор, False иначе
    """
    try:
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            admin_ids_str = os.getenv("ADMIN_IDS", "")
            
            if admin_ids_str:
                admin_list = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]
                return user_id in admin_list
        
        # Если не указаны админы, разрешаем всем (для тестирования)
        # В продакшене лучше требовать указания ADMIN_IDS
        return True  # Временно разрешаем всем
    except Exception:
        # В случае ошибки разрешаем всем (для простоты)
        return True

