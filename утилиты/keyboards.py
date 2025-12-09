"""
Модуль для создания клавиатур бота

Принцип разделения ответственности:
- Только создание и форматирование клавиатур
- Не содержит бизнес-логики
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Создает главную клавиатуру бота
    
    Args:
        user_id: ID пользователя (для будущих расширений)
    
    Returns:
        InlineKeyboardMarkup с кнопками главного меню
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Изучать материалы", callback_data="materials_list")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="leaderboard")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")]
    ])


def build_materials_level_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру выбора уровня сложности материалов
    
    Returns:
        InlineKeyboardMarkup с кнопками уровней
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔰 Базовый уровень", callback_data="materials_level:базовый")],
        [InlineKeyboardButton(text="⚡ Средний уровень", callback_data="materials_level:средний")],
        [InlineKeyboardButton(text="🔥 Продвинутый уровень", callback_data="materials_level:продвинутый")],
        [InlineKeyboardButton(text="📚 Все материалы", callback_data="materials_level:все")],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="home")]
    ])


def build_materials_list_keyboard(materials: list, user_progress: list) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком материалов
    
    Args:
        materials: Список материалов
        user_progress: Список ID изученных материалов
    
    Returns:
        InlineKeyboardMarkup с кнопками материалов
    """
    buttons = []
    
    for material in materials:
        material_id = material['id']
        title = material['title']
        is_studied = material_id in user_progress
        
        status = "✅" if is_studied else "📖"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {title}",
                callback_data=f"material:{material_id}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="📚 К уровням", callback_data="materials_list")])
    buttons.append([InlineKeyboardButton(text="🏠 Главная", callback_data="home")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_material_navigation_keyboard(
    material_id: int,
    has_test: bool,
    page_index: int = 0,
    total_pages: int = 1,
    is_last_page: bool = True
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру навигации для материала
    
    Args:
        material_id: ID материала
        has_test: Есть ли тест для материала
        page_index: Текущий индекс страницы (начиная с 0)
        total_pages: Общее количество страниц
        is_last_page: Является ли текущая страница последней
    
    Returns:
        InlineKeyboardMarkup с кнопками навигации
    """
    buttons = []
    
    # Кнопки навигации по страницам
    if total_pages > 1:
        nav_row = []
        if page_index > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"material_page:{material_id}:{page_index - 1}"
            ))
        nav_row.append(InlineKeyboardButton(
            text=f"📄 {page_index + 1}/{total_pages}",
            callback_data=f"material_info:{material_id}"
        ))
        if page_index < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                text="Далее ▶️",
                callback_data=f"material_page:{material_id}:{page_index + 1}"
            ))
        buttons.append(nav_row)
    
    # Кнопка теста (только на последней странице или если одна страница)
    if has_test and (is_last_page or total_pages == 1):
        buttons.append([
            InlineKeyboardButton(
                text="📝 Пройти тест",
                callback_data=f"test_start:{material_id}"
            )
        ])
    
    # Навигационные кнопки
    buttons.append([
        InlineKeyboardButton(text="📚 К списку материалов", callback_data="materials_list"),
        InlineKeyboardButton(text="🏠 Главная", callback_data="home")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_material_info_keyboard(material_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для страницы информации о материале
    
    Args:
        material_id: ID материала
    
    Returns:
        InlineKeyboardMarkup с кнопками
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Читать материал", callback_data=f"material:{material_id}")],
        [InlineKeyboardButton(text="📚 К списку", callback_data="materials_list")]
    ])


def build_back_to_home_keyboard() -> InlineKeyboardMarkup:
    """
    Создает простую клавиатуру с кнопкой "Главная"
    
    Returns:
        InlineKeyboardMarkup с кнопкой "Главная"
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главная", callback_data="home")]
    ])


def build_stats_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для страницы статистики
    
    Returns:
        InlineKeyboardMarkup с кнопками статистики
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="leaderboard")],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="home")]
    ])
