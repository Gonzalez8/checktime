import requests
import os
import datetime
import time
from dotenv import load_dotenv
from logger import bot_logger, error_logger

# Cargar variables de entorno
load_dotenv('/root/fichar/.env')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
FESTIVOS_FILE = '/root/fichar/festivos.txt'

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        bot_logger.info(f"Mensaje enviado a Telegram: {message}")
    except Exception as e:
        error_msg = f"Error enviando mensaje a Telegram: {e}"
        error_logger.error(error_msg)
        bot_logger.error(error_msg)

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 100}
    if offset:
        params["offset"] = offset
    try:
        response = requests.get(url, params=params, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        error_msg = f"Error obteniendo actualizaciones de Telegram: {e}"
        error_logger.error(error_msg)
        bot_logger.error(error_msg)
        return {"result": []}

def load_festivos():
    if not os.path.exists(FESTIVOS_FILE):
        bot_logger.warning(f"No se encontró el archivo de festivos: {FESTIVOS_FILE}")
        return []

    try:
        with open(FESTIVOS_FILE, 'r') as f:
            festivos = {line.strip() for line in f if line.strip()}
        return sorted(festivos, key=lambda d: datetime.datetime.strptime(d, "%Y-%m-%d"))
    except Exception as e:
        error_msg = f"Error cargando festivos: {e}"
        error_logger.error(error_msg)
        bot_logger.error(error_msg)
        return []

def save_festivos(festivos):
    try:
        festivos_ordenados = sorted(set(festivos), key=lambda d: datetime.datetime.strptime(d, "%Y-%m-%d"))
        with open(FESTIVOS_FILE, 'w') as f:
            for d in festivos_ordenados:
                f.write(f"{d}\n")
        bot_logger.info("Festivos guardados correctamente")
    except Exception as e:
        error_msg = f"Error guardando festivos: {e}"
        error_logger.error(error_msg)
        bot_logger.error(error_msg)
        raise

def add_festivo(date):
    try:
        datetime.datetime.strptime(date, "%Y-%m-%d")
        festivos = load_festivos()

        if date in festivos:
            bot_logger.warning(f"Intento de añadir festivo ya existente: {date}")
            send_telegram_message(f"⚠️ El festivo {date} ya está registrado.")
            return

        festivos.append(date)
        save_festivos(festivos)
        bot_logger.info(f"Festivo añadido: {date}")
        send_telegram_message(f"✅ Festivo añadido: {date}")
    except ValueError:
        error_msg = "Formato de fecha inválido"
        error_logger.error(error_msg)
        send_telegram_message("❌ Formato inválido. Usa: `/addfestivo YYYY-MM-DD`")
    except Exception as e:
        error_msg = f"Error al añadir festivo: {e}"
        error_logger.error(error_msg)
        send_telegram_message(f"❌ {error_msg}")

def delete_festivo(date):
    try:
        festivos = load_festivos()

        if date in festivos:
            festivos.remove(date)
            save_festivos(festivos)
            bot_logger.info(f"Festivo eliminado: {date}")
            send_telegram_message(f"✅ Festivo eliminado: {date}")
        else:
            bot_logger.warning(f"Intento de eliminar festivo inexistente: {date}")
            send_telegram_message(f"❌ Festivo {date} no encontrado.")
    except Exception as e:
        error_msg = f"Error al eliminar festivo: {e}"
        error_logger.error(error_msg)
        send_telegram_message(f"❌ {error_msg}")

def list_festivos():
    try:
        festivos = load_festivos()

        if not festivos:
            bot_logger.info("Lista de festivos vacía")
            send_telegram_message("📅 No hay festivos guardados.")
            return

        message = "📅 *Festivos registrados:*\n" + "\n".join(f"• `{d}`" for d in festivos)
        bot_logger.info("Lista de festivos enviada")
        send_telegram_message(message)
    except Exception as e:
        error_msg = f"Error al listar festivos: {e}"
        error_logger.error(error_msg)
        send_telegram_message(f"❌ {error_msg}")

def listen_telegram():
    bot_logger.info("Iniciando bot de Telegram")
    last_update_id = None

    while True:
        try:
            updates = get_updates(offset=(last_update_id + 1) if last_update_id else None)

            if "result" in updates:
                for update in updates["result"]:
                    last_update_id = update["update_id"]

                    if "message" in update:
                        message = update["message"]
                        chat_id = message["chat"]["id"]
                        text = message.get("text", "")

                        if str(chat_id) != TELEGRAM_CHAT_ID:
                            bot_logger.warning(f"Mensaje ignorado de chat no autorizado: {chat_id}")
                            continue

                        text = text.strip()
                        bot_logger.info(f"Comando recibido: {text}")

                        if text.startswith("/addfestivo"):
                            parts = text.split()
                            if len(parts) == 2:
                                add_festivo(parts[1])
                            else:
                                send_telegram_message("❌ Usa: `/addfestivo YYYY-MM-DD`")

                        elif text.startswith("/delfestivo"):
                            parts = text.split()
                            if len(parts) == 2:
                                delete_festivo(parts[1])
                            else:
                                send_telegram_message("❌ Usa: `/delfestivo YYYY-MM-DD`")

                        elif text == "/listfestivos":
                            list_festivos()

                        else:
                            bot_logger.warning(f"Comando no reconocido: {text}")
                            send_telegram_message("❓ Comando no reconocido. Usa `/addfestivo`, `/delfestivo` o `/listfestivos`.")

        except Exception as e:
            error_msg = f"Error en loop principal: {e}"
            error_logger.error(error_msg, exc_info=True)
            bot_logger.error(error_msg)

        time.sleep(5)

if __name__ == "__main__":
    listen_telegram()