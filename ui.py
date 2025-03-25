import os
import json
import time
import subprocess
import psutil
from collections import defaultdict
from PyQt5.QtWidgets import (
    QMainWindow, QStatusBar, QProgressBar, QLabel, QPushButton, QVBoxLayout, QWidget, QMessageBox, QFileDialog, QLineEdit, QHBoxLayout, QFrame, QGroupBox, QDesktopWidget
)
from PyQt5.QtCore import QTimer, QFileSystemWatcher, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWinExtras import QWinTaskbarButton
from copy_thread import CopyThread
from utils import *


class MainWindow(QMainWindow):
    def __init__(self):
        """Инициализация главного окна."""
        super().__init__()
        self.setWindowTitle("Epic Games ReStore")
        self.setWindowIcon(QIcon(":/icon.ico"))
        self.setFixedSize(400, 460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        self.center_window()

        self._init_ui()
        self._init_variables()
        self._init_timers()
        self._load_settings()

    def center_window(self):
        """Размещение окна в центре экрана."""
        screen_geometry = QDesktopWidget().screenGeometry()
        window_geometry = self.frameGeometry()
        window_geometry.moveCenter(screen_geometry.center())
        self.move(window_geometry.topLeft())

    def _init_ui(self):
        """Инициализация пользовательского интерфейса."""
        self.epic_path_label = QLabel("Путь к каталогу Epic Games Store:", self)
        self.epic_path_input = QLineEdit(self)
        self.epic_path_button = QPushButton("...", self)
        self.epic_path_button.clicked.connect(self.select_epic_path)
        self.epic_path_button.setFixedSize(30, 20)

        self.usb_path_label = QLabel("Путь к каталогу на флешке:", self)
        self.usb_path_input = QLineEdit(self)
        self.usb_path_button = QPushButton("...", self)
        self.usb_path_button.clicked.connect(self.select_usb_path)
        self.usb_path_button.setFixedSize(30, 20)

        self.warning_label = QLabel("ВНИМАНИЕ! Имена каталогов должны совпадать", self)

        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.start_button = QPushButton("Начать отслеживание", self)
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button = QPushButton("Остановить отслеживание", self)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False)
        self.status_label = QLabel("", self)

        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                border-top: 1px solid gray;
                background-color: #f0f0f0;  /* Цвет фона */
                padding: 5px;  /* Отступы внутри статус бара */
            }""")
        self.setStatusBar(self.status_bar)
        self.status_bar.setSizeGripEnabled(False)

        self._init_test_buttons()
        self._init_layout()

    def _init_test_buttons(self):
        """Инициализация тестовых кнопок."""
        self.test_launch_button = QPushButton("Запустить Epic Games", self)
        self.test_launch_button.clicked.connect(self.resume_epic)
        self.test_stop_button = QPushButton("Закрыть Epic Games", self)
        self.test_stop_button.clicked.connect(self.stop_epic)
        self.test_games_button = QPushButton("Список установленных игр", self)
        self.test_games_button.clicked.connect(lambda: show_games_info(*get_installed_games()))
        #self.test_create_button = QPushButton("[Создать тестовую папку и файл]", self)
        #self.test_create_button.clicked.connect(self.create_test_folder_and_file)
        #self.test_finish_copy_button = QPushButton("[Симулировать завершение копирования]", self)
        #self.test_finish_copy_button.clicked.connect(self.simulate_copy_finish)

        self.utilities_group = QGroupBox("Инструменты")
        utilities_layout = QVBoxLayout()
        utilities_layout.addWidget(self.test_launch_button)
        utilities_layout.addWidget(self.test_stop_button)
        utilities_layout.addWidget(self.test_games_button)
        #utilities_layout.addWidget(self.test_create_button)
        #utilities_layout.addWidget(self.test_finish_copy_button)
        self.utilities_group.setLayout(utilities_layout)

    def _init_layout(self):
        """Инициализация макета."""
        epic_layout = QHBoxLayout()
        epic_layout.addWidget(self.epic_path_input)
        epic_layout.addWidget(self.epic_path_button)

        usb_layout = QHBoxLayout()
        usb_layout.addWidget(self.usb_path_input)
        usb_layout.addWidget(self.usb_path_button)

        monitoring_buttons_layout = QHBoxLayout()
        monitoring_buttons_layout.addWidget(self.stop_button)
        monitoring_buttons_layout.addWidget(self.start_button)

        layout = QVBoxLayout()
        layout.addWidget(self.epic_path_label)
        layout.addLayout(epic_layout)
        layout.addWidget(self.usb_path_label)
        layout.addLayout(usb_layout)
        layout.addWidget(self.warning_label)
        layout.addWidget(self.line)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addLayout(monitoring_buttons_layout)
        layout.addWidget(self.utilities_group)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _init_variables(self):
        """Инициализация переменных."""
        self.epic_path = self.detect_epic_path()
        self.usb_path = self.get_farthest_drive()
        self.watcher = QFileSystemWatcher()
        self.tracked_folders = set()
        self.copy_thread = None
        self.new_folder_path = None
        self.usb_source_path = None
        self.timer = QTimer()
        self.delay_seconds = 5
        self.remaining_delay = self.delay_seconds
        self.epic_closed = False
        self.is_copying = False

    def _init_timers(self):
        """Инициализация таймеров."""
        self.stability_timer = QTimer()
        self.stability_timer.timeout.connect(self.start_copy_if_stable)
        self.stability_delay = 5
        self.last_change_time = 0

        self.taskbar_button = QWinTaskbarButton(self)
        self.taskbar_progress = self.taskbar_button.progress()
        self.taskbar_progress.setVisible(False)

    def _load_settings(self):
        """Загрузка настроек из файла."""
        self.settings_file = "settings.json"
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.epic_path = settings.get("epic_path", "")
                    self.usb_path = settings.get("usb_path", "")
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить настройки: {e}")
                self.epic_path = self.detect_epic_path()
                self.usb_path = self.get_farthest_drive()
        else:
            self.epic_path = self.detect_epic_path()
            self.usb_path = self.get_farthest_drive()

        self.epic_path_input.setText(self.epic_path)
        self.usb_path_input.setText(self.usb_path)

    def simulate_copy_finish(self):
        """Симулирует завершение копирования и проверки."""
        self.update_progress(100, 0.0, 0.0, self.copy_thread.copied_files if self.copy_thread else 0)
        self.update_integrity_progress(100)
        self.on_copy_finished()
        QMessageBox.information(self, "Успех", "Симуляция завершения копирования выполнена.")

    def create_test_folder_and_file(self):
        """Создает тестовую папку и файл в каталоге Epic Games."""
        test_folder_path = os.path.join(self.epic_path, "test_folder")
        test_file_path = os.path.join(test_folder_path, "test_file.txt")

        try:
            os.makedirs(test_folder_path, exist_ok=True)
            with open(test_file_path, "w", encoding="utf-8") as f:
                f.write("Это тестовый файл.")
            QMessageBox.information(self, "Успех", f"Создана тестовая папка и файл:\n{test_file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать тестовую папку или файл: {e}")

    def save_settings(self):
        """Сохраняет текущие настройки в файл."""
        settings = {
            "epic_path": self.epic_path_input.text(),
            "usb_path": self.usb_path_input.text(),
        }
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить настройки: {e}")

    def set_widgets_enabled(self, enabled):
        """Включает или отключает виджеты для выбора путей."""
        self.epic_path_input.setEnabled(enabled)
        self.epic_path_button.setEnabled(enabled)
        self.usb_path_input.setEnabled(enabled)
        self.usb_path_button.setEnabled(enabled)

    def detect_epic_path(self):
        """Автоматическое определение пути к Epic Games Store."""
        installed_games, invalid_path_games = get_installed_games()
        if not installed_games:
            return find_epic_games_path()

        path_count = defaultdict(int)
        for game in installed_games:
            parent_path = os.path.dirname(game["path"])
            path_count[parent_path] += 1

        return max(path_count, key=path_count.get)

    def get_available_drives(self):
        """Возвращает список доступных дисков."""
        return [f"{drive}:\\" for drive in string.ascii_uppercase if os.path.exists(f"{drive}:\\")]

    def get_farthest_drive(self):
        """Возвращает самый дальний доступный диск."""
        drives = self.get_available_drives()
        return drives[-1] if drives else "C:\\"

    def get_nearest_drive(self):
        """Возвращает самый ранний доступный диск."""
        drives = self.get_available_drives()
        return drives[0] if drives else "C:\\"

    def select_epic_path(self):
        """Открывает диалог выбора каталога Epic Games Store."""
        path = QFileDialog.getExistingDirectory(self, "Выберите каталог Epic Games Store", self.epic_path)
        if path:
            self.epic_path = path
            self.epic_path_input.setText(path)
            self.save_settings()

    def select_usb_path(self):
        """Открывает диалог выбора каталога на флешке."""
        path = QFileDialog.getExistingDirectory(self, "Выберите каталог на флешке", self.usb_path)
        if path:
            self.usb_path = path
            self.usb_path_input.setText(path)
            self.save_settings()

    def closeEvent(self, event):
        """Сохраняет настройки при закрытии программы."""
        self.save_settings()
        event.accept()

    def start_monitoring(self):
        """Начинает отслеживание каталога."""
        if not os.path.exists(self.epic_path):
            QMessageBox.critical(self, "Ошибка", "Каталог Epic Games не найден!")
            return
        
        existing_folders = set()
        if os.path.exists(self.epic_path):
            existing_folders = {f for f in os.listdir(self.epic_path) 
                            if os.path.isdir(os.path.join(self.epic_path, f))}
        self.tracked_folders = existing_folders
        self.watcher.directoryChanged.connect(self.on_directory_changed)
        self.watcher.addPath(self.epic_path)
        self.set_widgets_enabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_bar.showMessage("🟢 Отслеживание начато")

    def on_directory_changed(self, path):
        """Обрабатывает изменения в каталоге Epic Games."""
        if self.is_copying:
            self.status_bar.showMessage("Пропускаем изменения: идет процесс копирования")
            return

        try:
            if not os.path.exists(path):
                self.status_bar.showMessage(f"⚠️ Каталог удален: {path}")
                self.watcher.removePath(path)
                if path == self.epic_path:
                    self.stop_monitoring()
                return
            
            if path == self.epic_path:
                current_folders = {f for f in os.listdir(path) 
                                if os.path.isdir(os.path.join(path, f))}
                new_folders = current_folders - self.tracked_folders
                
                for folder in new_folders:
                    epic_folder = os.path.join(path, folder)
                    usb_folder = os.path.join(self.usb_path, folder)
                    
                    if os.path.exists(usb_folder):
                        self.status_bar.showMessage(f"✅ Найдена папка '{folder}' с совпадением на флешке")
                        self.watcher.addPath(epic_folder)
                        self.tracked_folders.add(folder)
                        files = [f for f in os.listdir(epic_folder) 
                                if os.path.isfile(os.path.join(epic_folder, f))]
                        if files:
                            self.status_bar.showMessage(f"📁 В новой папке есть файлы: '{folder}'")
                            self.prepare_copy(epic_folder, usb_folder)
            else:
                folder_name = os.path.basename(path)
                if folder_name in self.tracked_folders:
                    usb_folder = os.path.join(self.usb_path, folder_name)
                    
                    if os.path.exists(usb_folder):
                        files = [f for f in os.listdir(path) 
                                if os.path.isfile(os.path.join(path, f))]
                        
                        if files:
                            self.status_bar.showMessage(f"📁 Обнаружены файлы в '{folder_name}'")
                            self.prepare_copy(path, usb_folder)

        except Exception as e:
            error_msg = f"⚠️ Ошибка: {str(e)}"
            self.status_bar.showMessage(error_msg)

    def stop_monitoring(self):
        """Останавливает отслеживание."""
        try:
            self.watcher.directoryChanged.disconnect(self.on_directory_changed)
            for path in self.watcher.directories():
                self.watcher.removePath(path)
            self.tracked_folders.clear()
        except Exception as e:
            print(f"Ошибка при остановке мониторинга: {e}")

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_bar.showMessage("🔴 Отслеживание остановлено")
        self.set_widgets_enabled(True)

    def on_directory_changed(self, path):
        """Обрабатывает изменения в каталоге Epic Games."""
        if self.is_copying:
            self.status_bar.showMessage("Пропускаем изменения: идет процесс копирования")
            return

        try:
            if not os.path.exists(path):
                self.status_bar.showMessage(f"⚠️ Каталог удален: {path}")
                self.watcher.removePath(path)
                if path == self.epic_path:
                    self.stop_monitoring()
                return

            if path == self.epic_path:
                current_folders = {f for f in os.listdir(path) 
                                if os.path.isdir(os.path.join(path, f))}
                new_folders = current_folders - self.tracked_folders
                for folder in new_folders:
                    epic_folder = os.path.join(path, folder)
                    usb_folder = os.path.join(self.usb_path, folder)
                    if os.path.exists(usb_folder):
                        self.status_bar.showMessage(f"✅ Найдена новая папка '{folder}' с совпадением на флешке")
                        self.watcher.addPath(epic_folder)
                        self.tracked_folders.add(folder)
                        self.check_files_in_folder(epic_folder, usb_folder)
            else:
                folder_name = os.path.basename(path)
                if folder_name in self.tracked_folders:
                    usb_folder = os.path.join(self.usb_path, folder_name)
                    if os.path.exists(usb_folder):
                        self.check_files_in_folder(path, usb_folder)
        except Exception as e:
            error_msg = f"⚠️ Ошибка: {str(e)}"
            self.status_bar.showMessage(error_msg)

    def check_files_in_folder(self, epic_folder, usb_folder):
        """Проверяет файлы в папке, включая скрытые."""
        try:
            items = os.listdir(epic_folder)
            has_files = False
            for item in items:
                item_path = os.path.join(epic_folder, item)
                if os.path.isfile(item_path):
                    has_files = True
                    break
                elif os.path.isdir(item_path):
                    for root, dirs, files in os.walk(item_path):
                        if files:
                            has_files = True
                            break
                    if has_files:
                        break
            folder_name = os.path.basename(epic_folder)
            if has_files:
                self.status_bar.showMessage(f"📁 Обнаружены файлы в папке '{folder_name}'")
                self.prepare_copy(epic_folder, usb_folder)
            else:
                self.status_bar.showMessage(f"ℹ️ Папка '{folder_name}' пока не содержит файлов")
        except Exception as e:
            self.status_bar.showMessage(f"⚠️ Ошибка проверки папки: {str(e)}")

    def prepare_copy(self, epic_folder, usb_folder):
        """Подготовка к копированию после обнаружения файлов."""
        try:
            self.new_folder_path = epic_folder
            self.usb_source_path = usb_folder
            self.last_change_time = time.time()
            
            if not self.stability_timer.isActive():
                self.stability_timer.start(1000)
                folder_name = os.path.basename(epic_folder)
                self.status_bar.showMessage(f"⏳ Обнаружены файлы в '{folder_name}'. Ожидание стабильности...")
        except Exception as e:
            self.status_bar.showMessage(f"⚠️ Ошибка подготовки копирования: {str(e)}")

    def start_copy_if_stable(self):
        """Запускает копирование после стабилизации изменений."""
        current_time = time.time()
        time_diff = current_time - self.last_change_time
        if time_diff >= self.stability_delay:
            self.stability_timer.stop()
            folder_name = os.path.basename(self.new_folder_path)
            if not self.epic_closed:
                self.status_bar.showMessage(f"🛑 Закрываем Epic Games для '{folder_name}'...")
                self.stop_epic()
                self.epic_closed = True
                time.sleep(1)
            self.status_bar.showMessage(f"🚀 Начинаем копирование '{folder_name}'...")
            self.start_copy(self.usb_source_path, self.new_folder_path)
        else:
            remaining = int(self.stability_delay - time_diff)
            self.status_bar.showMessage(f"⏳ Ожидание стабильности: {remaining} сек...")
    
    def update_delay(self):
        """Обновляет отсчет задержки."""
        self.remaining_delay -= 1
        self.status_bar.showMessage(f"⏳ Ожидание {self.remaining_delay} сек...")
        if self.remaining_delay <= 0:
            self.timer.stop()
            if not self.epic_closed:
                self.stop_epic()
                self.epic_closed = True
            self.start_copy(self.usb_path, self.new_folder_path)

    def stop_epic(self):
        """Останавливает Epic Games Store."""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] == 'EpicGamesLauncher.exe':
                    proc.kill()
            QMessageBox.information(self, "Успех", "Epic Games Store остановлен.")
        except psutil.NoSuchProcess:
            QMessageBox.critical(self, "Ошибка", "Процесс Epic Games Launcher не найден.")
        except psutil.AccessDenied:
            QMessageBox.critical(self, "Ошибка", "Недостаточно прав для завершения процесса.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла непредвиденная ошибка: {e}")

    def start_copy(self, src, dst):
        """Начинает копирование."""
        if not os.path.exists(src):
            error_msg = f"❌ Ошибка: исходная папка не найдена на флешке: {src}"
            self.status_bar.showMessage(error_msg)
            QMessageBox.critical(self, "Ошибка", error_msg)
            return

        folder_name = os.path.basename(src)
        self.status_bar.showMessage(f"📊 Подготовка к копированию '{folder_name}'...")
        self.is_copying = True
        self.watcher.removePath(self.epic_path)
        total_size = sum(os.path.getsize(os.path.join(dirpath, filename)) 
                    for dirpath, dirnames, filenames in os.walk(src)
                    for filename in filenames)
        size_mb = total_size / (1024 * 1024)
        self.status_bar.showMessage(
            f"📦 Копирование '{folder_name}': "
            f"{len(os.listdir(src))} файлов, {size_mb:.2f} MB"
        )
        self.copy_thread = CopyThread(src, dst)
        self.copy_thread.progress_updated.connect(self.update_progress)
        self.copy_thread.copy_finished.connect(self.on_copy_finished)
        self.copy_thread.integrity_check_progress.connect(self.update_integrity_progress)
        self.copy_thread.start()

    def on_copy_finished(self):
        """Завершение копирования."""
        folder_name = os.path.basename(self.usb_source_path) if self.usb_source_path else "unknown"
        self.status_bar.showMessage(f"✅ Успешно скопировано: '{folder_name}'")
        self.is_copying = False
        self.watcher.addPath(self.epic_path)
        QTimer.singleShot(2000, lambda: (
            self.status_bar.showMessage("🔄 Запуск Epic Games..."),
            self.resume_epic()
        ))

    def update_progress(self, progress, speed, remaining_files, total_files, remaining_time):
        """Обновляет прогресс копирования."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(
            f"Скорость: {speed:.2f} МБ/с\n"
            f"Файлов: {total_files - remaining_files}/{total_files}\n"
            f"Осталось: {remaining_time}"
        )
        self.taskbar_progress.setValue(progress)

    def update_integrity_progress(self, progress):
        """Обновляет прогресс проверки целостности."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(
            f"Проверка целостности: {progress}%\n"
            f"Файлов проверено: {progress}%"
        )
        self.taskbar_progress.setValue(progress)

    def resume_epic(self):
        """Возобновляет загрузку через консольную команду."""
        try:
            subprocess.run(["start", "com.epicgames.launcher://apps"], shell=True, check=True)
            QMessageBox.information(self, "Успех", "Epic Games Store запущен")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить Epic Games Store: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла непредвиденная ошибка: {e}")

        self.stop_monitoring()
        self.progress_bar.setValue(0)
        self.status_label.setText("")
        self.status_bar.showMessage("⏳ Ожидание")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.taskbar_progress.setVisible(False)
        