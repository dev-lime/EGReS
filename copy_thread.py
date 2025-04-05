import os
import time
import hashlib
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal


class CopyThread(QThread):
    """Поток для копирования файлов и проверки целостности."""
    progress_updated = pyqtSignal(int, float, int, int, str)
    copy_finished = pyqtSignal()
    integrity_check_progress = pyqtSignal(int)

    def __init__(self, src, dst):
        super().__init__()
        self.src = src
        self.dst = dst
        self.total_size = 0
        self.copied_size = 0
        self.copied_files = 0
        self.total_files = 0
        self.running = True
        self.start_time = 0

    def run(self):
        """Основной метод, выполняющий копирование и проверку целостности."""
        try:
            self.start_time = time.time()
            self.calculate_total_size(self.src)
            self.count_total_files(self.src)
            
            if not os.path.exists(self.src):
                raise FileNotFoundError(f"Исходный путь не существует: {self.src}")
                
            if not os.path.exists(os.path.dirname(self.dst)):
                os.makedirs(os.path.dirname(self.dst), exist_ok=True)
                
            self.copy_files(self.src, self.dst)
            self.check_integrity(self.src, self.dst)
            self.copy_finished.emit()
        except Exception as e:
            error_msg = f"Произошла ошибка при копировании: {str(e)}"
            self.copy_finished.emit()  # Чтобы разблокировать интерфейс
            # Используем лямбду для отложенного вызова, так как мы не в основном потоке
            self.progress_updated.connect(lambda: QMessageBox.critical(None, "Ошибка", error_msg))

    def calculate_total_size(self, path):
        """Вычисляет общий размер данных для копирования."""
        if os.path.isdir(path):
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    self.calculate_total_size(item_path)
                else:
                    self.total_size += os.path.getsize(item_path)
        else:
            self.total_size += os.path.getsize(path)

    def count_total_files(self, path):
        """Подсчитывает общее количество файлов."""
        if os.path.isdir(path):
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    self.count_total_files(item_path)
                else:
                    self.total_files += 1
        else:
            self.total_files += 1

    def copy_files(self, src, dst):
        """Копирует файлы с заменой."""
        if not self.running:
            return

        if os.path.isdir(src):
            os.makedirs(dst, exist_ok=True)
            for item in os.listdir(src):
                src_item = os.path.join(src, item)
                dst_item = os.path.join(dst, item)
                self.copy_files(src_item, dst_item)
        else:
            self.copied_files += 1
            file_start_time = time.time()
            
            with open(src, 'rb') as f_src, open(dst, 'wb') as f_dst:
                while True:
                    if not self.running:
                        break
                    chunk = f_src.read(1024 * 1024)
                    if not chunk:
                        break
                    f_dst.write(chunk)
                    self.copied_size += len(chunk)
                    elapsed_time = time.time() - self.start_time
                    speed = (self.copied_size / (1024 * 1024)) / elapsed_time if elapsed_time > 0 else 0
                    progress = int((self.copied_size / self.total_size) * 100)
                    remaining_files = self.total_files - self.copied_files
                    if speed > 0:
                        remaining_bytes = self.total_size - self.copied_size
                        remaining_seconds = remaining_bytes / (speed * 1024 * 1024)
                        remaining_time_str = self.format_time(remaining_seconds)
                    else:
                        remaining_time_str = "--:--:--"
                    
                    self.progress_updated.emit(
                        progress, 
                        speed, 
                        remaining_files, 
                        self.total_files,
                        remaining_time_str
                    )

    def check_integrity(self, src, dst):
        """Проверяет целостность файлов."""
        checked_files = 0
        if os.path.isdir(src):
            for item in os.listdir(src):
                src_item = os.path.join(src, item)
                dst_item = os.path.join(dst, item)
                self.check_integrity(src_item, dst_item)
        else:
            if not self.verify_file_integrity(src, dst):
                QMessageBox.critical(None, "Ошибка", f"Файл {src} не прошел проверку целостности!")
            checked_files += 1
            progress = int((checked_files / self.total_files) * 100)
            self.integrity_check_progress.emit(progress)

    def verify_file_integrity(self, src, dst):
        """Проверяет целостность файла с помощью хеша."""
        if not os.path.exists(dst):
            return False
            
        if os.path.getsize(src) != os.path.getsize(dst):
            return False

        return self.calculate_md5(src) == self.calculate_md5(dst)

    def calculate_md5(self, file_path):
        """Вычисляет MD5 хеш файла."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def format_time(self, seconds):  # Добавьте self
        """Форматирует время в вид (дни, часы, минуты, секунды)"""
        if seconds < 0:
            return "00:00:00"
        
        seconds = int(seconds)
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        
        if days > 0:
            return f"{days}д {hours:02d}:{minutes:02d}:{seconds:02d}"
        elif hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    