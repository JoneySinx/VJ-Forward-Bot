#!/bin/bash

# Start Gunicorn (Web Server for Health Check)
gunicorn app:app &

# Start Telegram Bot
python3 main.py
