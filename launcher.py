"""Интерактивный лаунчер Taskly.

Делает всё сам: находит совместимый Python, создаёт venv, ставит зависимости,
настраивает .env, прогоняет миграции, спрашивает про тестовые данные
(логины и пароль) и запускает сайт, открывая браузер.

Запуск: start_taskly.bat  (или python launcher.py)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
IS_WINDOWS = os.name == "nt"
VENV_PY = PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
DEFAULTS = {
    "admin_user": "admin",
    "customer_user": "boss_anna",
    "freelancer_user": "devmax",
    "password": "Taskly2026",
}


# --------------------------------------------------------------------- #
# Ввод
# --------------------------------------------------------------------- #
def ask_yes_no(question, default=True):
    """Спросить «да/нет». Пустой ввод = значение по умолчанию."""
    suffix = "(y/n, по умолчанию y)" if default else "(y/n, по умолчанию n)"
    while True:
        answer = input(f"{question} {suffix}: ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes", "д", "да"):
            return True
        if answer in ("n", "no", "н", "нет"):
            return False
        print("  Введите y или n.")


def ask_text(question, default):
    """Спросить строку. Пустой ввод = значение по умолчанию."""
    answer = input(f"{question} [{default}]: ").strip()
    return answer or default


def fail(message):
    print(f"\n[ОШИБКА] {message}")
    input("\nНажмите Enter, чтобы закрыть окно...")
    sys.exit(1)


# --------------------------------------------------------------------- #
# Окружение
# --------------------------------------------------------------------- #
def find_python():
    """Возвращает список-команду для Python 3.10-3.14 или None.

    Django 5.1 официально поддерживает 3.10-3.13; на 3.14 сайт работает,
    но Django test client падает, поэтому 3.14 идёт в конце списка.
    """
    if not IS_WINDOWS:
        candidates = [[sys.executable]] + [["python3.%d" % v] for v in (13, 12, 11, 10, 14)]
    else:
        candidates = [["py", "-3.%d" % v] for v in (13, 12, 11, 10, 14)]
        candidates.append([sys.executable])

    for cmd in candidates:
        try:
            r = subprocess.run(
                [*cmd, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                capture_output=True, text=True,
            )
        except (OSError, ValueError):
            continue
        if r.returncode != 0:
            continue
        try:
            version = tuple(int(x) for x in r.stdout.strip().split("."))
        except ValueError:
            continue
        if (3, 10) <= version <= (3, 14):
            return cmd
    return None


def run(cmd, **kwargs):
    """Запустить команду с выводом в консоль."""
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT), **kwargs).returncode


def django_is_installed():
    return subprocess.run(
        [str(VENV_PY), "-c", "import django"], capture_output=True
    ).returncode == 0


def ensure_venv(py_cmd):
    if not VENV_PY.exists():
        print("Создаю виртуальное окружение...")
        if run([*py_cmd, "-m", "venv", str(PROJECT_ROOT / ".venv")], capture_output=True):
            fail("Не удалось создать виртуальное окружение.")

    if not django_is_installed():
        print("Устанавливаю зависимости (Django и др.)...")
        run([str(VENV_PY), "-m", "pip", "install", "--upgrade", "pip"], capture_output=True)
        run(
            [str(VENV_PY), "-m", "pip", "install",
             "-r", str(PROJECT_ROOT / "requirements.txt")],
            capture_output=True,
        )
        if not django_is_installed():
            fail("Не удалось установить зависимости из requirements.txt.")


def ensure_env_file():
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print("Создаю файл .env из .env.example...")
        shutil.copy(PROJECT_ROOT / ".env.example", env_file)


def has_users():
    """Есть ли уже пользователи в базе (для вопроса о пересоздании)."""
    r = subprocess.run(
        [str(VENV_PY), "manage.py", "shell", "-c",
         "from django.contrib.auth import get_user_model as m;"
         "print('YES' if m().objects.exists() else 'NO')"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    return "YES" in (r.stdout or "")


# --------------------------------------------------------------------- #
# Тестовые данные
# --------------------------------------------------------------------- #
def setup_demo_data():
    print()
    if not ask_yes_no("Заполнить базу тестовыми данными?", default=True):
        print("Тестовые данные не загружены (пустой сайт).")
        return

    print("  Просто Enter оставляет значение по умолчанию из скобок.")
    admin_user = ask_text("Логин администратора", DEFAULTS["admin_user"])
    customer_user = ask_text("Логин заказчика", DEFAULTS["customer_user"])
    freelancer_user = ask_text("Логин фрилансера", DEFAULTS["freelancer_user"])
    demo_password = ask_text("Пароль для всех тестовых аккаунтов", DEFAULTS["password"])

    flush = []
    if has_users():
        print()
        if ask_yes_no(
            "В базе уже есть данные. Удалить ВСЕ заказы, отклики и сообщения\n"
            "и создать демо-данные заново?",
            default=False,
        ):
            flush = ["--flush"]
        else:
            print("  Старые данные остаются, добавляются только новые записи.")

    print("\nЗаполняю базу тестовыми данными...")
    cmd = [
        str(VENV_PY), "manage.py", "seed_demo",
        "--password", demo_password,
        "--admin-user", admin_user,
        "--customer-user", customer_user,
        "--freelancer-user", freelancer_user,
        *flush,
    ]
    if run(cmd):
        fail("Не удалось заполнить базу. Проверь введённые логины и пароль.")


# --------------------------------------------------------------------- #
def main():
    print("=" * 60)
    print("  Taskly — запуск сайта")
    print("=" * 60)
    print()

    py_cmd = find_python()
    if not py_cmd:
        fail(
            "Не найден Python версии 3.10 - 3.14.\n\n"
            "  Установи Python 3.12 с https://www.python.org/downloads/\n"
            '  (при установке отметь галочку "Add Python to PATH").\n'
            "  После этого запусти этот файл ещё раз."
        )
    print(f"Найден Python: {' '.join(py_cmd)}")

    ensure_venv(py_cmd)
    ensure_env_file()

    print("Готовлю базу данных...")
    run([str(VENV_PY), "manage.py", "makemigrations"], capture_output=True)
    if run([str(VENV_PY), "manage.py", "migrate"], capture_output=True):
        fail("Не удалось применить миграции.")

    setup_demo_data()

    print()
    print("=" * 60)
    print("  Сайт:            http://127.0.0.1:8000/")
    print("  Админ-панель:    http://127.0.0.1:8000/admin/")
    print("  Закрой это окно, чтобы остановить сайт.")
    print("=" * 60)
    print()

    def open_browser():
        time.sleep(3)
        try:
            webbrowser.open("http://127.0.0.1:8000/")
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()

    run([str(VENV_PY), "manage.py", "runserver", "127.0.0.1:8000", "--noreload"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nОстановлено.")
