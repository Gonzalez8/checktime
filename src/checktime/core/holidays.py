import os
import datetime
from typing import List, Set
from ..utils.logger import bot_logger, error_logger
from ..config.settings import FESTIVOS_FILE

class HolidayManager:
    """Gestor de días festivos."""
    
    def __init__(self, festivos_file: str = FESTIVOS_FILE):
        """
        Inicializa el gestor de festivos.
        
        Args:
            festivos_file (str): Ruta al archivo de festivos
        """
        self.festivos_file = festivos_file
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(self.festivos_file), exist_ok=True)
        # Crear el archivo si no existe
        if not os.path.exists(self.festivos_file):
            with open(self.festivos_file, 'w') as f:
                f.write("")
            bot_logger.info(f"Archivo de festivos creado: {self.festivos_file}")
    
    def load_holidays(self) -> Set[str]:
        """
        Carga los festivos desde el archivo.
        
        Returns:
            Set[str]: Conjunto de fechas festivas
        """
        try:
            with open(self.festivos_file, 'r') as f:
                festivos = {line.strip() for line in f if line.strip()}
            return festivos
        except Exception as e:
            error_msg = f"Error cargando festivos: {e}"
            error_logger.error(error_msg)
            bot_logger.error(error_msg)
            return set()
    
    def save_holidays(self, holidays: Set[str]) -> None:
        """
        Guarda los festivos en el archivo.
        
        Args:
            holidays (Set[str]): Conjunto de fechas festivas
        """
        try:
            holidays_ordered = sorted(holidays, key=lambda d: datetime.datetime.strptime(d, "%Y-%m-%d"))
            with open(self.festivos_file, 'w') as f:
                for date in holidays_ordered:
                    f.write(f"{date}\n")
            bot_logger.info("Festivos guardados correctamente")
        except Exception as e:
            error_msg = f"Error guardando festivos: {e}"
            error_logger.error(error_msg)
            bot_logger.error(error_msg)
            raise
    
    def add_holiday(self, date: str) -> bool:
        """
        Añade un nuevo día festivo.
        
        Args:
            date (str): Fecha en formato YYYY-MM-DD
        
        Returns:
            bool: True si se añadió correctamente, False en caso contrario
        """
        try:
            # Validar formato de fecha
            datetime.datetime.strptime(date, "%Y-%m-%d")
            holidays = self.load_holidays()

            if date in holidays:
                bot_logger.warning(f"Intento de añadir festivo ya existente: {date}")
                return False

            holidays.add(date)
            self.save_holidays(holidays)
            bot_logger.info(f"Festivo añadido: {date}")
            return True
        except ValueError:
            error_msg = "Formato de fecha inválido"
            error_logger.error(error_msg)
            return False
        except Exception as e:
            error_msg = f"Error al añadir festivo: {e}"
            error_logger.error(error_msg)
            return False
    
    def remove_holiday(self, date: str) -> bool:
        """
        Elimina un día festivo.
        
        Args:
            date (str): Fecha en formato YYYY-MM-DD
        
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        try:
            holidays = self.load_holidays()

            if date not in holidays:
                bot_logger.warning(f"Intento de eliminar festivo inexistente: {date}")
                return False

            holidays.remove(date)
            self.save_holidays(holidays)
            bot_logger.info(f"Festivo eliminado: {date}")
            return True
        except Exception as e:
            error_msg = f"Error al eliminar festivo: {e}"
            error_logger.error(error_msg)
            return False
    
    def is_holiday(self, date: str = None) -> bool:
        """
        Verifica si una fecha es festiva.
        
        Args:
            date (str, optional): Fecha a verificar en formato YYYY-MM-DD.
                                Si no se proporciona, se usa la fecha actual.
        
        Returns:
            bool: True si es festivo, False en caso contrario
        """
        if date is None:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        holidays = self.load_holidays()
        return date in holidays
    
    def get_holidays(self) -> List[str]:
        """
        Obtiene la lista de festivos.
        
        Returns:
            List[str]: Lista ordenada de fechas festivas
        """
        holidays = self.load_holidays()
        return sorted(holidays, key=lambda d: datetime.datetime.strptime(d, "%Y-%m-%d")) 