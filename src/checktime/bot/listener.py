import time
from typing import Optional, Dict, Any
from ..utils.logger import bot_logger, error_logger
from ..utils.telegram import TelegramClient
from ..core.holidays import HolidayManager

class TelegramBotListener:
    """Cliente para escuchar y procesar comandos de Telegram."""
    
    def __init__(self, telegram_client: Optional[TelegramClient] = None, holiday_manager: Optional[HolidayManager] = None):
        """
        Inicializa el listener de Telegram.
        
        Args:
            telegram_client (Optional[TelegramClient]): Cliente de Telegram
            holiday_manager (Optional[HolidayManager]): Gestor de festivos
        """
        self.telegram = telegram_client or TelegramClient()
        self.holiday_manager = holiday_manager or HolidayManager()
        self.last_update_id = None
    
    def process_command(self, message: Dict[str, Any]) -> None:
        """
        Procesa un comando recibido.
        
        Args:
            message (Dict[str, Any]): Mensaje recibido
        """
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
        
        if str(chat_id) != self.telegram.chat_id:
            bot_logger.warning(f"Mensaje ignorado de chat no autorizado: {chat_id}")
            return
        
        bot_logger.info(f"Comando recibido: {text}")
        
        if text.startswith("/addfestivo"):
            parts = text.split()
            if len(parts) == 2:
                self.add_holiday(parts[1])
            else:
                self.telegram.send_message("❌ Usa: `/addfestivo YYYY-MM-DD`")
        
        elif text.startswith("/delfestivo"):
            parts = text.split()
            if len(parts) == 2:
                self.remove_holiday(parts[1])
            else:
                self.telegram.send_message("❌ Usa: `/delfestivo YYYY-MM-DD`")
        
        elif text == "/listfestivos":
            self.list_holidays()
        
        else:
            bot_logger.warning(f"Comando no reconocido: {text}")
            self.telegram.send_message("❓ Comando no reconocido. Usa `/addfestivo`, `/delfestivo` o `/listfestivos`.")
    
    def add_holiday(self, date: str) -> None:
        """
        Añade un día festivo.
        
        Args:
            date (str): Fecha en formato YYYY-MM-DD
        """
        try:
            if self.holiday_manager.add_holiday(date):
                self.telegram.send_message(f"✅ Festivo añadido: {date}")
            else:
                self.telegram.send_message(f"⚠️ El festivo {date} ya está registrado.")
        except ValueError:
            self.telegram.send_message("❌ Formato inválido. Usa: `/addfestivo YYYY-MM-DD`")
        except Exception as e:
            error_msg = f"Error al añadir festivo: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}")
    
    def remove_holiday(self, date: str) -> None:
        """
        Elimina un día festivo.
        
        Args:
            date (str): Fecha en formato YYYY-MM-DD
        """
        try:
            if self.holiday_manager.remove_holiday(date):
                self.telegram.send_message(f"✅ Festivo eliminado: {date}")
            else:
                self.telegram.send_message(f"❌ Festivo {date} no encontrado.")
        except Exception as e:
            error_msg = f"Error al eliminar festivo: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}")
    
    def list_holidays(self) -> None:
        """Lista los próximos días festivos del año."""
        try:
            from datetime import datetime
            import sqlite3
            import os
            
            current_date = datetime.now().date()
            current_year = current_date.year
            
            # Use the configured database from environment
            import os
            db_path = os.getenv('DATABASE_URL', 'sqlite:////data/checktime.db')
            if db_path.startswith('sqlite:///'):
                db_path = db_path[10:]  # Remove the sqlite:/// prefix
            
            if not os.path.exists(db_path):
                self.telegram.send_message("❌ No se pudo encontrar la base de datos")
                return
            
            # Acceder directamente a SQLite
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Obtener todos los festivos
            cursor.execute("SELECT date, description FROM holiday")
            all_holidays = cursor.fetchall()
            
            if not all_holidays:
                self.telegram.send_message("📅 No hay festivos guardados.")
                conn.close()
                return
            
            # Filtrar para mostrar solo los próximos festivos del año actual
            upcoming_holidays = []
            for date_str, desc in all_holidays:
                holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if holiday_date >= current_date and holiday_date.year == current_year:
                    upcoming_holidays.append((date_str, desc))
            
            if not upcoming_holidays:
                self.telegram.send_message("📅 No hay festivos próximos para este año.")
                conn.close()
                return
            
            # Crear el mensaje
            message = f"📅 *Próximos festivos del año {current_year}:*\n"
            for date_str, desc in sorted(upcoming_holidays, key=lambda x: datetime.strptime(x[0], "%Y-%m-%d")):
                holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                days_remaining = (holiday_date - current_date).days
                day_text = "hoy" if days_remaining == 0 else f"en {days_remaining} día{'s' if days_remaining != 1 else ''}"
                message += f"- {date_str} ({desc}): {day_text}\n"
            
            conn.close()
            self.telegram.send_message(message)
        except Exception as e:
            error_msg = f"Error al listar festivos: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}")
    
    def listen(self) -> None:
        """Inicia el bucle de escucha de comandos."""
        bot_logger.info("Iniciando bot de Telegram")
        
        while True:
            try:
                updates = self.telegram.get_updates(
                    offset=(self.last_update_id + 1) if self.last_update_id else None
                )
                
                if "result" in updates:
                    for update in updates["result"]:
                        self.last_update_id = update["update_id"]
                        
                        if "message" in update:
                            self.process_command(update["message"])
            
            except Exception as e:
                error_msg = f"Error en loop principal: {e}"
                error_logger.error(error_msg, exc_info=True)
                bot_logger.error(error_msg)
            
            time.sleep(5)

def main():
    """Función principal para ejecutar el bot."""
    listener = TelegramBotListener()
    listener.listen()

if __name__ == "__main__":
    main() 