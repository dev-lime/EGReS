import sys
import os
import shutil
import time
import hashlib
import winreg
import string
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStatusBar, QProgressBar, QLabel, QPushButton, QVBoxLayout, QWidget, QMessageBox, QFileDialog, QLineEdit, QHBoxLayout, QFrame
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QFileSystemWatcher, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWinExtras import QWinTaskbarButton, QWinTaskbarProgress  # Импорт для работы с панелью задач Windows


class CopyThread(QThread):
    # Сигналы для обновления прогресса и статистики
    progress_updated = pyqtSignal(int, float, float, int)  # прогресс, скорость (МБ/с), оставшееся время, скопировано файлов
    copy_finished = pyqtSignal()
    integrity_check_progress = pyqtSignal(int)  # прогресс проверки целостности

    def __init__(self, src, dst):
        super().__init__()
        self.src = src
        self.dst = dst
        self.total_size = 0
        self.copied_size = 0
        self.copied_files = 0
        self.total_files = 0  # Добавляем атрибут для хранения общего количества файлов
        self.running = True

    def run(self):
        self.calculate_total_size(self.src)
        self.count_total_files(self.src)  # Подсчитываем общее количество файлов
        self.copy_files(self.src, self.dst)
        self.copy_finished.emit()
        self.check_integrity(self.src, self.dst)

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
        """Копирует файлы с отображением прогресса."""
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
            start_time = time.time()
            with open(src, 'rb') as f_src, open(dst, 'wb') as f_dst:
                while True:
                    if not self.running:
                        break
                    chunk = f_src.read(1024 * 1024)  # Чтение по 1 МБ
                    if not chunk:
                        break
                    f_dst.write(chunk)
                    self.copied_size += len(chunk)
                    elapsed_time = time.time() - start_time
                    speed = (self.copied_size / (1024 * 1024)) / elapsed_time if elapsed_time > 0 else 0  # Скорость в МБ/с
                    remaining_time = (self.total_size - self.copied_size) / (speed * 1024 * 1024) if speed > 0 else 0  # Оставшееся время в секундах
                    progress = int((self.copied_size / self.total_size) * 100)
                    self.progress_updated.emit(progress, speed, remaining_time, self.copied_files)

    def check_integrity(self, src, dst):
        """Проверяет целостность файлов."""
        if os.path.isdir(src):
            for item in os.listdir(src):
                src_item = os.path.join(src, item)
                dst_item = os.path.join(dst, item)
                self.check_integrity(src_item, dst_item)
        else:
            if not self.verify_file_integrity(src, dst):
                QMessageBox.critical(self, "Ошибка", f"Файл {src} не прошел проверку целостности!")
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Epic Games ReStore")
        self.setWindowIcon(QIcon(":/icon.ico"))
        self.setGeometry(100, 100, 400, 300)

        # Запрет на изменение размера окна и максимизацию
        self.setFixedSize(400, 300)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)

        # Виджеты
        self.epic_path_label = QLabel("Путь к каталогу Epic Games Store:", self)
        self.epic_path_input = QLineEdit(self)
        self.epic_path_button = QPushButton("...", self)
        self.epic_path_button.setFixedSize(30, 20)

        self.usb_path_label = QLabel("Путь к каталогу на флешке:", self)
        self.usb_path_input = QLineEdit(self)
        self.usb_path_button = QPushButton("...", self)
        self.usb_path_button.setFixedSize(30, 20)

        self.progress_bar = QProgressBar(self)

        self.start_button = QPushButton("Начать отслеживание", self)
        self.stop_button = QPushButton("Остановить отслеживание", self)
        self.stop_button.setEnabled(False)

        self.status_label = QLabel("", self)

        # Тестовая кнопка для запуска Epic Games
        self.test_launch_button = QPushButton("Тест: Запустить Epic Games", self)
        self.test_launch_button.clicked.connect(self.resume_epic)

        # Линия для визуального отделения статус бара
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ожидание")

        # Макет
        epic_layout = QHBoxLayout()
        epic_layout.addWidget(self.epic_path_input)
        epic_layout.addWidget(self.epic_path_button)

        usb_layout = QHBoxLayout()
        usb_layout.addWidget(self.usb_path_input)
        usb_layout.addWidget(self.usb_path_button)

        layout = QVBoxLayout()
        layout.addWidget(self.epic_path_label)
        layout.addLayout(epic_layout)
        layout.addWidget(self.usb_path_label)
        layout.addLayout(usb_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.test_launch_button)  # Добавляем тестовую кнопку
        layout.addWidget(self.line)  # Добавляем линию

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Переменные
        self.epic_path = self.detect_epic_path()  # Автоматическое определение пути к Epic Games Store
        self.usb_path = "E:/"  # Путь по умолчанию к флешке
        self.watcher = QFileSystemWatcher()
        self.copy_thread = None
        self.new_folder_path = None  # Путь к новой созданной папке
        self.timer = QTimer()  # Таймер для задержки
        self.delay_seconds = 5  # Задержка в 5 секунд
        self.remaining_delay = self.delay_seconds  # Оставшееся время задержки
        self.epic_closed = False  # Флаг для отслеживания состояния Epic Games
        self.is_copying = False  # Флаг для отслеживания состояния копирования

        # Инициализация полей
        self.epic_path_input.setText(self.epic_path)
        self.usb_path_input.setText(self.usb_path)

        # Инициализация QWinTaskbarButton для отображения прогресса на иконке в панели задач
        self.taskbar_button = QWinTaskbarButton(self)
        self.taskbar_progress = self.taskbar_button.progress()
        self.taskbar_progress.setVisible(False)  # Скрываем прогресс по умолчанию

        # Сигналы
        self.epic_path_button.clicked.connect(self.select_epic_path)
        self.usb_path_button.clicked.connect(self.select_usb_path)
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.watcher.directoryChanged.connect(self.on_directory_changed)
        self.timer.timeout.connect(self.update_delay)

    def find_epic_games_path(self):
        """Поиск пути к Epic Games Store на всех доступных дисках."""
        # Стандартные пути
        standard_paths = [
            os.path.join(os.environ["ProgramFiles"], "Epic Games"),
            os.path.join(os.environ["ProgramFiles(x86)"], "Epic Games"),
        ]

        # Проверка стандартных путей
        for path in standard_paths:
            launcher_path = os.path.join(path, "Launcher", "Portal", "Binaries", "Win32", "EpicGamesLauncher.exe")
            if os.path.exists(launcher_path):
                return os.path.dirname(launcher_path)

        # Поиск в реестре
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Epic Games\EpicGamesLauncher")
            install_location = winreg.QueryValueEx(reg_key, "AppDataPath")[0]
            if os.path.exists(os.path.join(install_location, "EpicGamesLauncher.exe")):
                return install_location
        except FileNotFoundError:
            pass

        # Поиск на всех доступных дисках
        for drive in string.ascii_uppercase:
            drive_path = f"{drive}:\\"
            if os.path.exists(drive_path):  # Проверяем, существует ли диск
                for root, dirs, files in os.walk(drive_path):
                    if "EpicGamesLauncher.exe" in files:
                        return root

        return None

    def detect_epic_path(self):
        """Автоматическое определение пути к Epic Games Store."""
        epic_path = self.find_epic_games_path()
        if epic_path:
            return epic_path
        else:
            QMessageBox.critical(self, "Ошибка", "Epic Games Store не найден на компьютере!")
            return ""

    def select_epic_path(self):
        """Открывает диалог выбора каталога Epic Games Store."""
        path = QFileDialog.getExistingDirectory(self, "Выберите каталог Epic Games Store", self.epic_path)
        if path:
            self.epic_path = path
            self.epic_path_input.setText(path)

    def select_usb_path(self):
        """Открывает диалог выбора каталога на флешке."""
        path = QFileDialog.getExistingDirectory(self, "Выберите каталог на флешке", self.usb_path)
        if path:
            self.usb_path = path
            self.usb_path_input.setText(path)

    def start_monitoring(self):
        """Начинает отслеживание каталога."""
        if not os.path.exists(self.epic_path):
            QMessageBox.critical(self, "Ошибка", "Каталог Epic Games Store не найден!")
            return

        self.watcher.addPath(self.epic_path)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_bar.showMessage("Отслеживание")

    def stop_monitoring(self):
        """Останавливает отслеживание."""
        self.watcher.removePath(self.epic_path)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_bar.showMessage("Отслеживание остановлено.")

    def on_directory_changed(self, path):
        """Обрабатывает изменения в каталоге."""
        if self.is_copying:  # Если идет копирование, игнорируем изменения
            return

        # Проверяем, появилась ли новая папка
        folders = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]
        if folders:
            self.new_folder_path = os.path.join(path, folders[-1])  # Последняя созданная папка
            self.watcher.addPath(self.new_folder_path)  # Начинаем отслеживать новую папку

        # Проверяем, появился ли файл в новой папке
        if self.new_folder_path and os.path.exists(self.new_folder_path):
            files = [f for f in os.listdir(self.new_folder_path) if os.path.isfile(os.path.join(self.new_folder_path, f))]
            if files:
                # Запускаем таймер на 5 секунд
                self.remaining_delay = self.delay_seconds
                self.timer.start(1000)  # Таймер срабатывает каждую секунду
                self.status_bar.showMessage(f"Ожидание {self.remaining_delay} сек...")

    def update_delay(self):
        """Обновляет отсчет задержки."""
        self.remaining_delay -= 1
        self.status_bar.showMessage(f"Ожидание {self.remaining_delay} сек...")

        if self.remaining_delay <= 0:
            self.timer.stop()
            if not self.epic_closed:
                self.stop_epic()
                self.epic_closed = True
            self.start_copy(self.usb_path, self.new_folder_path)

    def stop_epic(self):
        """Останавливает Epic Games Store."""
        try:
            os.system(f"taskkill /f /im EpicGamesLauncher.exe")
            QMessageBox.information(self, "Успех", "Epic Games Store остановлен.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось остановить Epic Games Store: {e}")

    def start_copy(self, src, dst):
        """Начинает копирование данных."""
        if not os.path.exists(src):
            QMessageBox.critical(self, "Ошибка", "Каталог для копирования не найден!")
            return

        # Определяем имя папки на флешке
        folder_name = os.path.basename(os.path.normpath(src))
        # Создаем путь для копирования
        dst_path = os.path.join(dst, folder_name)

        self.is_copying = True  # Устанавливаем флаг копирования
        self.watcher.removePath(self.epic_path)  # Отключаем отслеживание

        self.copy_thread = CopyThread(src, dst_path)
        self.copy_thread.progress_updated.connect(self.update_progress)
        self.copy_thread.copy_finished.connect(self.on_copy_finished)
        self.copy_thread.integrity_check_progress.connect(self.update_integrity_progress)
        self.copy_thread.start()
        self.status_bar.showMessage("Копирование")

    def on_copy_finished(self):
        """Обрабатывает завершение копирования."""
        self.is_copying = False  # Сбрасываем флаг копирования
        self.watcher.addPath(self.epic_path)  # Включаем отслеживание
        self.resume_epic()

    def update_progress(self, progress, speed, remaining_time, copied_files):
        """Обновляет прогресс и статистику."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(
            f"Прогресс: {progress}%\n"
            f"Скорость: {speed:.2f} МБ/с\n"
            f"Осталось: {int(remaining_time)} сек\n"
            f"Скопировано файлов: {copied_files}"
        )

        # Обновляем прогресс на иконке в панели задач
        if not self.taskbar_progress.isVisible():
            self.taskbar_progress.setVisible(True)
        self.taskbar_progress.setValue(progress)

    def update_integrity_progress(self, progress):
        """Обновляет прогресс проверки целостности."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(f"Проверка целостности: {progress}%")

        # Обновляем прогресс на иконке в панели задач
        if not self.taskbar_progress.isVisible():
            self.taskbar_progress.setVisible(True)
        self.taskbar_progress.setValue(progress)

    def resume_epic(self):
        """Возобновляет загрузку."""
        launcher_path = os.path.join(self.epic_path, "EpicGamesLauncher.exe")
        if os.path.exists(launcher_path):
            try:
                # Используем subprocess.Popen для запуска Epic Games Launcher
                subprocess.Popen([launcher_path], shell=True)
                QMessageBox.information(self, "Успех", "Epic Games Store запущен. Загрузка возобновлена.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось запустить Epic Games Store: {e}")
        else:
            QMessageBox.critical(self, "Ошибка", "Файл EpicGamesLauncher.exe не найден!")

        # Возвращаем программу в исходное состояние
        self.stop_monitoring()  # Останавливаем отслеживание
        self.progress_bar.setValue(0)  # Сбрасываем прогресс
        self.status_label.setText("")  # Очищаем статус
        self.status_bar.showMessage("Ожидание")  # Возвращаем статус в исходное состояние
        self.start_button.setEnabled(True)  # Включаем кнопку "Начать отслеживание"
        self.stop_button.setEnabled(False)  # Отключаем кнопку "Остановить отслеживание"

        # Скрываем прогресс на иконке в панели задач
        self.taskbar_progress.setVisible(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
    