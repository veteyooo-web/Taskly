r"""Точка входа Taskly в режиме единого EXE-файла (PyInstaller).

При запуске EXE:
1. готовит каталог данных (по умолчанию %LOCALAPPDATA%\Taskly);
2. применяет миграции к локальной SQLite-базе;
3. спрашивает, нужно ли создать/обновить тестовые данные;
4. при наличии демо-данных выводит логин, пароль и ссылку на сайт;
5. поднимает веб-сервер waitress на http://127.0.0.1:<порт> и открывает браузер.

Вся статика раздаётся WhiteNoise, шаблоны и приложения лежат внутри архива.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Все импорты Django — только после установки переменной окружения
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

DEMO_INFO_FILE = ".demo_info.json"
DEFAULTS = {
    "admin_user": "admin",
    "customer_user": "boss_anna",
    "freelancer_user": "devmax",
    "password": "Taskly2026",
}


# ------------------------------------------------------------------ #
# Интерактивный ввод
# ------------------------------------------------------------------ #
def _stdin_available() -> bool:
    """True если stdin можно читать (не редирект в pipe)."""
    try:
        return sys.stdin.isatty()
    except OSError:
        return False


def ask_yes_no(question: str, default: bool = True) -> bool:
    """Спросить «да/нет». Пустой ввод = значение по умолчанию."""
    if not _stdin_available():
        return default
    suffix = "(y/n, по умолчанию y)" if default else "(y/n, по умолчанию n)"
    while True:
        try:
            answer = input(f"{question} {suffix}: ").strip().lower()
        except EOFError:
            return default
        if not answer:
            return default
        if answer in ("y", "yes", "д", "да"):
            return True
        if answer in ("n", "no", "н", "нет"):
            return False
        print("  Введите y или n.")


def ask_text(question: str, default: str) -> str:
    """Спросить строку. Пустой ввод = значение по умолчанию."""
    if not _stdin_available():
        return default
    try:
        answer = input(f"{question} [{default}]: ").strip()
    except EOFError:
        return default
    return answer or default


# ------------------------------------------------------------------ #
# Порт
# ------------------------------------------------------------------ #
def find_free_port(host: str, start: int = 8000, attempts: int = 11) -> int:
    """Возвращает первый свободный порт начиная с start."""
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise OSError(f"Не найден свободный порт в диапазоне {start}-{start + attempts - 1}")


# ------------------------------------------------------------------ #
# Демо-информация (сохраняется и читается из каталога данных)
# ------------------------------------------------------------------ #
def _demo_info_path(base_dir: Path) -> Path:
    return base_dir / DEMO_INFO_FILE


def _load_demo_info(base_dir: Path) -> dict | None:
    p = _demo_info_path(base_dir)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save_demo_info(base_dir: Path, info: dict) -> None:
    try:
        _demo_info_path(base_dir).write_text(
            json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


# ------------------------------------------------------------------ #
# Подготовка базы и демо-данных
# ------------------------------------------------------------------ #
def prepare_database(base_dir: Path) -> dict | None:
    """Мигрирует БД, спрашивает про демо-данные и заполняет базу.

    Возвращает словарь с демо-данными или None (если пользователь отказался).
    """
    import django

    django.setup()

    from django.conf import settings

    # WhiteNoise при старте предупреждает, если STATIC_ROOT не существует;
    # collectstatic в EXE-режиме не нужен (статика идёт через finders).
    Path(settings.STATIC_ROOT).mkdir(exist_ok=True)

    from django.core.management import call_command

    print("Проверяю и обновляю базу данных...")
    call_command("migrate", run_syncdb=True, verbosity=0)

    from apps.users.models import User

    existing = User.objects.exists()

    # --- Если база уже не пустая и пользователь не хочет пересоздавать ---
    if existing:
        # Спрашиваем, хочет ли пользователь обновить демо-данные
        if ask_yes_no(
            "В базе уже есть данные. Обновить тестовые данные?", default=True
        ):
            if ask_yes_no(
                "Это удалит ВСЕ заказы, отклики и сообщения\n"
                "и создаст демо-данные заново. Продолжить?",
                default=False,
            ):
                # Берём текущие значения или новые
                info = _load_demo_info(base_dir) or DEFAULTS.copy()
                admin_user = ask_text("Логин администратора", info.get("admin_user", DEFAULTS["admin_user"]))
                customer_user = ask_text("Логин заказчика", info.get("customer_user", DEFAULTS["customer_user"]))
                freelancer_user = ask_text("Логин фрилансера", info.get("freelancer_user", DEFAULTS["freelancer_user"]))
                demo_password = ask_text("Пароль для всех тестовых аккаунтов", info.get("password", DEFAULTS["password"]))

                print("\nПересоздаю демо-данные...")
                call_command(
                    "seed_demo",
                    "--flush",
                    "--password", demo_password,
                    "--admin-user", admin_user,
                    "--customer-user", customer_user,
                    "--freelancer-user", freelancer_user,
                    verbosity=0,
                )
                info = {
                    "admin_user": admin_user,
                    "customer_user": customer_user,
                    "freelancer_user": freelancer_user,
                    "password": demo_password,
                }
                _save_demo_info(base_dir, info)
                return info
            else:
                # Не пересоздаём — возвращаем сохранённые данные
                return _load_demo_info(base_dir)
        else:
            # Не пересоздаём — возвращаем сохранённые данные
            return _load_demo_info(base_dir)

    # --- База пустая: спрашиваем про демо-данные ---
    if not ask_yes_no("Создать базу с тестовыми данными?", default=True):
        print("Тестовые данные не загружены (пустой сайт).")
        return None

    print("  Просто Enter оставляет значение по умолчанию из скобок.")
    admin_user = ask_text("Логин администратора", DEFAULTS["admin_user"])
    customer_user = ask_text("Логин заказчика", DEFAULTS["customer_user"])
    freelancer_user = ask_text("Логин фрилансера", DEFAULTS["freelancer_user"])
    demo_password = ask_text("Пароль для всех тестовых аккаунтов", DEFAULTS["password"])

    print("\nСоздаю демо-данные...")
    call_command(
        "seed_demo",
        "--password", demo_password,
        "--admin-user", admin_user,
        "--customer-user", customer_user,
        "--freelancer-user", freelancer_user,
        verbosity=0,
    )
    info = {
        "admin_user": admin_user,
        "customer_user": customer_user,
        "freelancer_user": freelancer_user,
        "password": demo_password,
    }
    _save_demo_info(base_dir, info)
    return info


# ------------------------------------------------------------------ #
# Точка входа
# ------------------------------------------------------------------ #
def main() -> None:
    # Определяем каталог данных (BASE_DIR из settings.py)
    import config.settings as settings_mod

    base_dir = settings_mod.BASE_DIR
    base_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 56)
    print("  Taskly — единый файл (запуск без установки)")
    print("=" * 56)
    print()

    try:
        demo_info = prepare_database(base_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"\n[ОШИБКА] Не удалось подготовить базу: {exc}")
        try:
            input("\nНажмите Enter, чтобы закрыть окно...")
        except EOFError:
            pass
        raise SystemExit(1) from exc

    host = os.environ.get("TASKLY_HOST", "127.0.0.1")
    port_env = os.environ.get("TASKLY_PORT")
    port = int(port_env) if port_env else find_free_port(host)
    url = f"http://{host}:{port}/"

    print()
    print(f"  Сайт:         {url}")
    print(f"  Админ-панель: {url}admin/")

    if demo_info:
        print()
        print("  Демо-доступы:")
        print(f"    Админ:            {demo_info['admin_user']} / {demo_info['password']}")
        print(f"    Заказчик:         {demo_info['customer_user']} / {demo_info['password']}")
        print(f"    Фрилансер:        {demo_info['freelancer_user']} / {demo_info['password']}")
        print()

    print("  Закройте это окно, чтобы остановить сайт.")
    print()
    sys.stdout.flush()

    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    from config.wsgi import application  # импортируется после django.setup()
    from waitress import serve

    try:
        serve(application, host=host, port=port)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
