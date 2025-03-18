import os
import time
import hashlib
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal


class CopyThread(QThread):
    """Поток для копирования файлов и проверки целостности."""
    progress_updated = pyqtSignal(int, float, float, int)
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

    def run(self):
        """Основной метод, выполняющий копирование и проверку целостности."""
        try:
            self.calculate_total_size(self.src)
            self.count_total_files(self.src)
            self.copy_files(self.src, self.dst)
            self.check_integrity(self.src, self.dst)
            self.copy_finished.emit()
        except Exception as e:
            QMessageBox.critical(None, "Ошибка", f"Произошла ошибка при копировании: {e}")

    def calculate_total_size(self, path):
        """Вычисляет общий размер данных для копирования."""
        if os.path.isdir(path):
            for item in os.listdir(path):
                if item.startswith('.'):
                    continue
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
                if item.startswith('.'):
                    continue
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    self.count_total_files(item_path)
                else:
                    self.total_files += 1
        else:
            self.total_files += 1

    def copy_files(self, src, dst):
        """Копирует файлы с заменой, исключая папки, начинающиеся с точки."""
        if not self.running:
            return

        if os.path.isdir(src):
            os.makedirs(dst, exist_ok=True)
            for item in os.listdir(src):
                if item.startswith('.'):
                    continue
                src_item = os.path.join(src, item)
                dst_item = os.path.join(dst, item)
                self.copy_files(src_item, dst_item)
        else:
            self.copied_files += 1
            start_time = time.time()
            with open(src, 'rb') as f_src, open(dst, 'wb') as f_dst:
                while True:
                    if not self.running:
                        break
                    chunk = f_src.read(1024 * 1024)
                    if not chunk:
                        break
                    f_dst.write(chunk)
                    self.copied_size += len(chunk)
                    elapsed_time = time.time() - start_time
                    speed = (self.copied_size / (1024 * 1024)) / elapsed_time if elapsed_time > 0 else 0
                    remaining_time = (self.total_size - self.copied_size) / (speed * 1024 * 1024) if speed > 0 else 0
                    progress = int((self.copied_size / self.total_size) * 100)
                    self.progress_updated.emit(progress, speed, remaining_time, self.copied_files)

    def check_integrity(self, src, dst):
        """Проверяет целостность файлов."""
        if os.path.isdir(src):
            for item in os.listdir(src):
                if item.startswith('.'):
                    continue
                src_item = os.path.join(src, item)
                dst_item = os.path.join(dst, item)
                self.check_integrity(src_item, dst_item)
        else:
            if not self.verify_file_integrity(src, dst):
                QMessageBox.critical(None, "Ошибка", f"Файл {src} не прошел проверку целостности!")
            self.integrity_check_progress.emit(int((self.copied_files / self.total_files) * 100))

    def verify_file_integrity(self, src, dst):
        """Проверяет целостность файла с помощью хеша."""
        if os.path.getsize(src) != os.path.getsize(dst):
            return False

        hash_src = self.calculate_md5(src)
        hash_dst = self.calculate_md5(dst)
        return hash_src == hash_dst

    def calculate_md5(self, file_path):
        """Вычисляет MD5 хеш файла."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    