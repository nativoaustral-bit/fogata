#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Cargar variables de entorno (servidor HostGator o local)
    base_dir = Path(__file__).resolve().parent
    env_candidates = [
        Path('/home1/paulocis/apps/fogata/secrets/.env'),
        base_dir.parent / 'secrets' / '.env',
        base_dir / '.env',
    ]
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
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
    main()
