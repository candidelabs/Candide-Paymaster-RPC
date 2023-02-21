#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

import argparse

def main():
    """Run administrative tasks."""
    parser = argparse.ArgumentParser(description='Overwrite values in os.environ with optional command-line arguments')
    parser.add_argument('--port', help='port number', type=int)
    parser.add_argument('--chainId', help='The Ethereum Network chain ID', type=int)
    parser.add_argument('--HTTPProvider', help='The Ethereum Network URL HTTP provider', type=str)
    args, remaining_argv = parser.parse_known_args()

    if args.chainId:
        os.environ["chainId"] = str(args.chainId)
    if args.HTTPProvider:
        os.environ["HTTPProvider"] = args.HTTPProvider
    if args.port:
        os.environ["PORT"] = str(args.port)
    
    if 'runserver' in remaining_argv:
        if args.port:
            remaining_argv += ['{}'.format(args.port)]

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bundler.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(['manage.py'] + remaining_argv)

if __name__ == "__main__":
    main()
