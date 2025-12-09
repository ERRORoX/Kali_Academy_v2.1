"""
Главный файл запуска бота Kali Linux Academy

Этот файл отвечает за:
- Инициализацию бота и всех его компонентов
- Загрузку конфигурации (токен из .env файла)
- Создание диспетчера и подключение всех обработчиков
- Инициализацию базы данных
- Запуск polling (получение обновлений от Telegram API)

Структура запуска:
1. Настройка логирования
2. Загрузка токена бота из .env
3. Валидация токена
4. Создание экземпляра бота и диспетчера
5. Подключение всех роутеров (handlers)
6. Инициализация базы данных
7. Начало получения обновлений

Пример использования:
    python3 bot.py

Требования:
    - Файл .env с токеном TELEGRAM_BOT_TOKEN или BOT_TOKEN
    - База данных SQLite (создается автоматически)
"""
import asyncio
import logging
import os

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# Импортируем конфигурацию
from config import APP_ROOT

# Импортируем главный роутер со всеми обработчиками
from обработчики import router


async def main() -> None:
    """
    Основная функция запуска бота
    
    Эта функция выполняет всю инициализацию и запускает бота.
    Все ошибки логируются и приводят к остановке программы.
    
    Шаги выполнения:
    1. Настройка логирования для отслеживания работы бота
    2. Загрузка токена из переменных окружения
    3. Валидация токена (проверка на пустой/плейсхолдер)
    4. Создание диспетчера для обработки сообщений
    5. Подключение всех обработчиков через роутер
    6. Создание экземпляра бота
    7. Проверка работоспособности токена
    8. Инициализация базы данных
    9. Начало polling (бесконечный цикл получения обновлений)
    
    Raises:
        RuntimeError: Если токен не найден или невалиден
    """
    # Настройка логирования
    # INFO уровень покажет все важные события работы бота
    logging.basicConfig(level=logging.INFO)

    # ===== ЗАГРУЗКА ТОКЕНА =====
    # Токен можно указать в переменных окружения или в файле .env
    # Приоритет: сначала ищем TELEGRAM_BOT_TOKEN, затем BOT_TOKEN
    env_path = APP_ROOT / ".env"
    load_dotenv(dotenv_path=env_path, override=False)
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    
    # Проверка наличия токена
    if not token:
        raise RuntimeError(
            "Не задан токен. Укажите TELEGRAM_BOT_TOKEN или BOT_TOKEN в .env"
        )
    
    # Валидация токена - убираем пробелы и проверяем, что это не плейсхолдер
    token = token.strip()
    if "PASTE_YOUR_TOKEN_HERE" in token or token == "":
        raise RuntimeError(
            "В .env оставлен плейсхолдер токена. "
            "Вставьте реальный токен от @BotFather"
        )

    # ===== СОЗДАНИЕ ДИСПЕТЧЕРА =====
    # Dispatcher - это центральный объект, который маршрутизирует все обновления
    # MemoryStorage - хранилище состояний в памяти (FSM для aiogram)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Подключаем главный роутер, который включает все обработчики:
    # - commands.py - команды (/start, /leaderboard, и т.д.)
    # - callbacks.py - обработка нажатий на кнопки
    # - tests.py - обработка тестов
    # - admin.py - административные команды
    dp.include_router(router)
    
    # ===== СОЗДАНИЕ И ЗАПУСК БОТА =====
    # async with гарантирует корректное закрытие соединений при остановке
    async with Bot(
        token=token, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    ) as bot:
        # Проверка токена - попытка получить информацию о боте
        # Если токен неверный, получим исключение
        try:
            bot_info = await bot.get_me() 
            print(f"Бот запущен: @{bot_info.username}") 
            logging.info(f"Бот запущен: @{bot_info.username}") 
        except Exception as e:
            logging.error("Проверка токена не пройдена: %r", e)
            raise RuntimeError(f"Ошибка при проверке токена: {str(e)}")

        # ===== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ =====
        # База данных создаётся автоматически при первом подключении
        from утилиты.database import db
        # Добавляем дефолтные материалы/тесты, если отсутствуют
        db.seed_default_content()
        materials = db.get_all_materials()
        # Обновляем рейтинги всех пользователей при запуске
        db.update_all_ratings()
        logging.info(f"База данных готова: {len(materials)} материалов в базе")

        # ===== ЗАПУСК POLLING =====
        # start_polling начинает бесконечный цикл получения обновлений от Telegram
        # allowed_updates определяет, какие типы обновлений получать
        # dp.resolve_used_update_types() автоматически определит нужные типы
        # на основе зарегистрированных обработчиков
        logging.info("Бот готов к работе! Ожидание сообщений...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


# ===== ТОЧКА ВХОДА =====
# Этот код выполняется только при прямом запуске файла (не при импорте)

if __name__ == "__main__":
    try:
        # asyncio.run() создаёт event loop и запускает async функцию main()
        # После завершения main() event loop автоматически закрывается
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        # Корректная обработка остановки (Ctrl+C или системный сигнал)
        # Просто выходим без ошибок
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        # Логируем любые другие ошибки для отладки
        logging.exception("Критическая ошибка при работе бота: %s", e)
        raise
