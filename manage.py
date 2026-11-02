#!/usr/bin/env python
"""Django's command-line utility for administrative tasks.

Автоматически поднимается в .venv, поэтому `python manage.py runserver`
работает даже без ручной активации окружения.
"""
import os
import sys
from pathlib import Path


def _use_project_venv():
    """Перезапускает процесс интерпретатором из .venv, если он есть."""
    base_dir = Path(__file__).resolve().parent
    venv_python = base_dir / '.venv' / 'bin' / 'python'
    if not venv_python.exists():
        return
    # sys.prefix надёжнее сравнения путей: симлинк .venv/bin/python
    # указывает на тот же системный интерпретатор, что и текущий.
    if getattr(sys, 'base_prefix', sys.prefix) != sys.prefix:
        return  # уже внутри venv
    os.execv(str(venv_python), [str(venv_python), *sys.argv])


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    _use_project_venv()
    main()
