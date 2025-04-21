import os
import datetime
from typing import List, Set
from ..utils.logger import bot_logger, error_logger

class HolidayManager:
    """Gestor de días festivos."""
    
    def __init__(self, holidays_file=None):
        """
        Inicializa el gestor de festivos.
        """
        pass
    
    def _require_app_context(self):
        """
        Ensure that we're in an application context.
        """
        try:
            from flask import current_app
            # First check if we're already in an app context
            current_app._get_current_object()
            return None
        except Exception:
            # If not, create a temporary application context
            from ..web import create_app
            app = create_app()
            return app.app_context()
    
    def load_holidays(self) -> Set[str]:
        """
        Carga los festivos desde la base de datos.
        
        Returns:
            Set[str]: Conjunto de fechas festivas
        """
        ctx = None
        try:
            ctx = self._require_app_context()
            if ctx:
                ctx.push()
            
            try:
                # Intenta usar el modelo Holiday primero
                from ..web.models import Holiday
                holidays = set(Holiday.get_all_dates())
                if holidays:
                    return holidays
            except Exception as db_error:
                error_msg = f"Error al acceder a los festivos a través del modelo: {db_error}"
                error_logger.warning(error_msg)
                bot_logger.warning(error_msg)
            
            # Si falla, intenta con SQLite directamente
            import sqlite3
            import os
            
            # Use the configured database URL
            db_url = os.getenv('DATABASE_URL', 'sqlite:////data/checktime.db')
            if db_url.startswith('sqlite:///'):
                db_path = db_url[10:]  # Remove sqlite:/// prefix
                
                if os.path.exists(db_path):
                    # Accede a la base de datos usando SQLite directamente
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT strftime('%Y-%m-%d', date) FROM holiday")
                    holidays = set([row[0] for row in cursor.fetchall()])
                    conn.close()
                    return holidays
            
            # Si no se encuentra la base de datos, devuelve un conjunto vacío
            return set()
        except Exception as e:
            error_msg = f"Error cargando festivos: {e}"
            error_logger.error(error_msg)
            bot_logger.error(error_msg)
            return set()
        finally:
            if ctx:
                try:
                    ctx.pop()
                except Exception:
                    # Context may have already been popped
                    pass
    
    def save_holidays(self, holidays: Set[str]):
        """
        Guarda los festivos en la base de datos.
        
        Args:
            holidays (Set[str]): Conjunto de fechas festivas
        """
        ctx = None
        try:
            ctx = self._require_app_context()
            if ctx:
                ctx.push()
            
            # Import here to avoid circular imports
            from ..web.models import Holiday, db
            
            # Delete all holidays
            Holiday.query.delete()
            
            # Add new holidays if any
            for date_str in holidays:
                date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                holiday = Holiday(date=date_obj, description="Added via save_holidays")
                db.session.add(holiday)
                
            db.session.commit()
            bot_logger.info("Holidays saved successfully")
        except Exception as e:
            error_msg = f"Error saving holidays: {e}"
            error_logger.error(error_msg)
            bot_logger.error(error_msg)
            raise
        finally:
            if ctx:
                try:
                    ctx.pop()
                except Exception:
                    # Context may have already been popped
                    pass
    
    def add_holiday(self, date: str, description: str = None) -> bool:
        """
        Añade un nuevo día festivo.
        
        Args:
            date (str): Fecha en formato YYYY-MM-DD
            description (str, optional): Descripción del festivo. Si no se proporciona, se usa una predeterminada.
        
        Returns:
            bool: True si se añadió correctamente, False en caso contrario
        """
        try:
            # Validar formato de fecha
            date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
            
            ctx = self._require_app_context()
            if ctx:
                ctx.push()
            
            # Import here to avoid circular imports
            from ..web.models import Holiday, db
            
            # Check if holiday already exists
            existing = Holiday.query.filter_by(date=date_obj).first()
            if existing:
                bot_logger.warning(f"Intento de añadir festivo ya existente: {date}")
                if ctx:
                    ctx.pop()
                return False
            
            # Add to database
            holiday_description = description if description else f"Added via API on {datetime.datetime.now()}"
            holiday = Holiday(date=date_obj, description=holiday_description)
            db.session.add(holiday)
            db.session.commit()
            
            bot_logger.info(f"Festivo añadido: {date}")
            
            if ctx:
                ctx.pop()
                
            return True
        except ValueError:
            error_msg = f"Formato de fecha inválido: {date}"
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
            # Validar formato de fecha
            date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
            
            ctx = self._require_app_context()
            if ctx:
                ctx.push()
            
            # Import here to avoid circular imports
            from ..web.models import Holiday, db
            
            # Find and delete the holiday
            holiday = Holiday.query.filter_by(date=date_obj).first()
            if not holiday:
                bot_logger.warning(f"Intento de eliminar festivo inexistente: {date}")
                if ctx:
                    ctx.pop()
                return False
            
            db.session.delete(holiday)
            db.session.commit()
            
            bot_logger.info(f"Festivo eliminado: {date}")
            
            if ctx:
                ctx.pop()
                
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
    
    def clear_holidays(self) -> bool:
        """
        Remove all holidays from the holiday file.
        
        Returns:
            bool: True if holidays were cleared successfully, False otherwise
        """
        try:
            self.save_holidays(set())
            return True
        except Exception as e:
            error_logger.error(f"Error clearing holidays: {e}")
            return False 