from airflow.providers.telegram.hooks.telegram import TelegramHook
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN_TELEGRAM")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram_success_message(context): # на вход принимаем словарь со контекстными переменными
    hook = TelegramHook(
                        token=TOKEN,
                        chat_id=CHAT_ID)
    dag = context['dag']
    run_id = context['run_id']
    
    message = f'Исполнение DAG {dag} с id={run_id} прошло успешно!' # определение текста сообщения
    hook.send_message({
        'chat_id': CHAT_ID,
        'text': message,
        "parse_mode": None
    }) # отправление сообщения 


def send_telegram_failure_message(context): # на вход принимаем словарь со контекстными переменными
    hook = TelegramHook(
                        token=TOKEN,
                        chat_id=CHAT_ID)
    dag = context['dag']
    run_id = context['run_id']
    task_instance_key_str = context['task_instance_key_str']
    
    message = f"{dag} провален( run_id {run_id}. Описание: {task_instance_key_str}"
    hook.send_message({
        'chat_id': CHAT_ID,
        'text': message,
        "parse_mode": None
    }) 