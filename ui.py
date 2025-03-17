import os
import json
import time
import subprocess
import psutil
from PyQt5.QtWidgets import (
    QMainWindow, QStatusBar, QProgressBar, QLabel, QPushButton, QVBoxLayout, QWidget, QMessageBox, QFileDialog, QLineEdit, QHBoxLayout, QFrame, QGroupBox
)
from PyQt5.QtCore import QTimer, QFileSystemWatcher, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWinExtras import QWinTaskbarButton
from copy_thread import CopyThread  # Импортируем CopyThread из отдельного модуля
from utils import *


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Epic Games ReStore")
        self.setWindowIcon(QIcon(":/icon.ico"))
        self.setGeometry(100, 100, 400, 460)  # Начальные размеры окна

        self.setFixedSize(400, 460)
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

        self.warning_label = QLabel("ВНИМАНИЕ! Имена каталогов должны совпадать", self)

        self.progress_bar = QProgressBar(self)

        self.start_button = QPushButton("Начать отслеживание", self)
        self.stop_button = QPushButton("Остановить отслеживание", self)
        self.stop_button.setEnabled(False)

        self.status_label = QLabel("", self)

        # Тестовые кнопки
        self.test_launch_button = QPushButton("Запустить Epic Games", self)
        self.test_launch_button.clicked.connect(self.resume_epic)
        
        self.test_stop_button = QPushButton("Закрыть Epic Games", self)
        self.test_stop_button.clicked.connect(self.stop_epic)
        
        self.test_games_button = QPushButton("Список установленных игр", self)
        self.test_games_button.clicked.connect(lambda: show_games_info(*get_installed_games()))

        # Создаем группу для тестовых кнопок
        self.utilities_group = QGroupBox("Инструменты")

        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        # Создаем статус бар
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                border-top: 1px solid gray;
                background-color: #f0f0f0;  /* Цвет фона */
                padding: 5px;  /* Отступы внутри статус бара */
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.setSizeGripEnabled(False)
        self.status_bar.showMessage("Ожидание")

        # Макет
        epic_layout = QHBoxLayout()
        epic_layout.addWidget(self.epic_path_input)
        epic_layout.addWidget(self.epic_path_button)

        usb_layout = QHBoxLayout()
        usb_layout.addWidget(self.usb_path_input)
        usb_layout.addWidget(self.usb_path_button)

        # Горизонтальный макет для кнопок "Начать отслеживание" и "Остановить отслеживание"
        monitoring_buttons_layout = QHBoxLayout()
        monitoring_buttons_layout.addWidget(self.stop_button)
        monitoring_buttons_layout.addWidget(self.start_button)

        # Тестовые кнопки
        self.test_create_button = QPushButton("Создать тестовую папку и файл", self)
        self.test_create_button.clicked.connect(self.create_test_folder_and_file)

        self.test_modify_button = QPushButton("Симулировать изменение файла", self)
        self.test_modify_button.clicked.connect(self.modify_test_file)

        # Добавляем тестовые кнопки в группу "Инструменты"
        utilities_layout = QVBoxLayout()
        utilities_layout.addWidget(self.test_launch_button)
        utilities_layout.addWidget(self.test_stop_button)
        utilities_layout.addWidget(self.test_games_button)
        utilities_layout.addWidget(self.test_create_button)
        utilities_layout.addWidget(self.test_modify_button)
        self.utilities_group.setLayout(utilities_layout)

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

        # Переменные
        self.epic_path = self.detect_epic_path()  # Автоматическое определение пути к Epic Games Store
        self.usb_path = self.get_farthest_drive()  # Путь по умолчанию к флешке
        self.watcher = QFileSystemWatcher()
        self.copy_thread = None
        self.new_folder_path = None  # Путь к новой созданной папке
        self.timer = QTimer()  # Таймер для задержки
        self.delay_seconds = 5  # Задержка в 5 секунд
        self.remaining_delay = self.delay_seconds  # Оставшееся время задержки
        self.epic_closed = False  # Флаг для отслеживания состояния Epic Games
        self.is_copying = False  # Флаг для отслеживания состояния копирования

        # Новый таймер для проверки стабильности каталога
        self.stability_timer = QTimer()
        self.stability_timer.timeout.connect(self.start_copy_if_stable)
        self.stability_delay = 5
        self.last_change_time = 0  # Время последнего изменения

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
        
        # Загружаем сохраненные пути при запуске
        self.settings_file = "settings.json"
        self.load_settings()

        # Автоматически подбираем размер окна
        #self.adjustSize()


    def create_test_folder_and_file(self):
        """Создает тестовую папку и файл в каталоге Epic Games."""
        test_folder_path = os.path.join(self.epic_path, "test_folder")
        test_file_path = os.path.join(test_folder_path, "test_file.txt")

        try:
            # Создаем папку, если её нет
            os.makedirs(test_folder_path, exist_ok=True)

            # Создаем тестовый файл
            with open(test_file_path, "w", encoding="utf-8") as f:
                f.write("Это тестовый файл.")

            QMessageBox.information(self, "Успех", f"Создана тестовая папка и файл:\n{test_file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать тестовую папку или файл: {e}")

    def modify_test_file(self):
        """Симулирует изменение тестового файла через несколько секунд."""
        test_folder_path = os.path.join(self.epic_path, "test_folder")
        test_file_path = os.path.join(test_folder_path, "test_file.txt")

        if not os.path.exists(test_file_path):
            QMessageBox.warning(self, "Ошибка", "Тестовый файл не найден. Сначала создайте его.")
            return

        # Запускаем таймер для изменения файла через 5 секунд
        self.modify_timer = QTimer()
        self.modify_timer.timeout.connect(lambda: self._modify_file(test_file_path))
        self.modify_timer.start(5000)  # 5 секунд
        QMessageBox.information(self, "Информация", "Файл будет изменен через 5 секунд.")

    def _modify_file(self, file_path):
        """Изменяет содержимое тестового файла."""
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write("\nФайл был изменен.")
            QMessageBox.information(self, "Успех", f"Файл изменен:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось изменить файл: {e}")
        finally:
            self.modify_timer.stop()
            
    def load_settings(self):
        """Загружает сохраненные настройки из файла."""
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

        # Устанавливаем значения в поля ввода
        self.epic_path_input.setText(self.epic_path)
        self.usb_path_input.setText(self.usb_path)

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
        """
        Включает или отключает виджеты для выбора путей.
        :param enabled: Если True, виджеты включаются. Если False, отключаются.
        """
        self.epic_path_input.setEnabled(enabled)
        self.epic_path_button.setEnabled(enabled)
        self.usb_path_input.setEnabled(enabled)
        self.usb_path_button.setEnabled(enabled)

    def detect_epic_path(self):
        """
        Автоматическое определение пути к Epic Games Store.
        Возвращает путь с наибольшим количеством установленных игр.
        """
        # Получаем список установленных игр
        installed_games, invalid_path_games = get_installed_games()

        if not installed_games:
            return find_epic_games_path()

        # Считаем количество игр для каждого пути
        path_count = defaultdict(int)
        for game in installed_games:
            parent_path = os.path.dirname(game["path"])  # Получаем родительскую папку
            path_count[parent_path] += 1

        # Находим путь с наибольшим количеством игр
        most_common_path = max(path_count, key=path_count.get)

        return most_common_path

    def get_available_drives(self):
        """Возвращает список доступных дисков."""
        drives = []
        for drive in range(ord('A'), ord('Z') + 1):
            drive_letter = chr(drive) + ":\\"
            if os.path.exists(drive_letter):
                drives.append(drive_letter)
        return drives

    def get_farthest_drive(self):
        """Возвращает самый дальний доступный диск."""
        drives = self.get_available_drives()
        if drives:
            return drives[-1]  # Возвращаем последний диск в списке
        return "C:\\"  # Если диски не найдены, возвращаем C:\ по умолчанию

    def get_nearest_drive(self):
        """Возвращает самый ранний доступный диск."""
        drives = self.get_available_drives()
        if drives:
            return drives[0]
        return "C:\\"

    def select_epic_path(self):
        """Открывает диалог выбора каталога Epic Games Store."""
        path = QFileDialog.getExistingDirectory(self, "Выберите каталог Epic Games Store", self.epic_path)
        if path:
            self.epic_path = path
            self.epic_path_input.setText(path)
            self.save_settings()  # Сохраняем настройки после изменения

    def select_usb_path(self):
        """Открывает диалог выбора каталога на флешке."""
        path = QFileDialog.getExistingDirectory(self, "Выберите каталог на флешке", self.usb_path)
        if path:
            self.usb_path = path
            self.usb_path_input.setText(path)
            self.save_settings()  # Сохраняем настройки после изменения
    
    def closeEvent(self, event):
        """Сохраняет настройки при закрытии программы."""
        self.save_settings()
        event.accept()

    def start_monitoring(self):
        """Начинает отслеживание каталога."""
        if not os.path.exists(self.epic_path):
            QMessageBox.critical(self, "Ошибка", "Каталог Epic Games не найден!")
            return
        self.set_widgets_enabled(False)
        self.watcher.addPath(self.epic_path)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_bar.showMessage("Отслеживание")

    def stop_monitoring(self):
        """Останавливает отслеживание."""
        self.watcher.removePath(self.epic_path)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_bar.showMessage("Ожидание")
        self.set_widgets_enabled(True)

    def on_directory_changed(self, path):
        """Обрабатывает изменения в каталоге."""
        if self.is_copying:  # Если идет копирование, игнорируем изменения
            return

        try:
            # Проверяем, существует ли каталог
            if not os.path.exists(path):
                self.status_bar.showMessage(f"Каталог не найден: {path}")
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
                    # Запускаем таймер стабильности
                    self.stability_timer.start(1000)  # Проверка каждую секунду
                    self.status_bar.showMessage(f"Ожидание стабильности")

        except FileNotFoundError:
            self.status_bar.showMessage(f"Каталог не найден: {path}")
        except PermissionError:
            self.status_bar.showMessage(f"Нет доступа к каталогу: {path}")
        except Exception as e:
            self.status_bar.showMessage(f"Ошибка: {str(e)}")
    
    def start_copy_if_stable(self):
        """Проверяет, завершены ли изменения, и начинает копирование."""
        current_time = time.time()
        if current_time - self.last_change_time >= self.stability_delay:
            # Если изменений не было в течение 10 секунд, останавливаем таймер и начинаем копирование
            self.stability_timer.stop()
            if not self.epic_closed:
                self.stop_epic()
                self.epic_closed = True
            self.start_copy(self.usb_path, self.new_folder_path)
        else:
            # Если изменения продолжаются, обновляем статус
            remaining_time = int(self.stability_delay - (current_time - self.last_change_time))
            self.status_bar.showMessage(f"Ожидание стабильности... {remaining_time} сек")

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

        # Создаем поток копирования
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
        """Возобновляет загрузку через консольную команду."""
        try:
            # Используем команду start для запуска URI Epic Games Launcher
            subprocess.run(["start", "com.epicgames.launcher://apps"], shell=True, check=True)
            QMessageBox.information(self, "Успех", "Epic Games Store запущен")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить Epic Games Store: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла непредвиденная ошибка: {e}")

        # Возвращаем программу в исходное состояние
        self.stop_monitoring()  # Останавливаем отслеживание
        self.progress_bar.setValue(0)  # Сбрасываем прогресс
        self.status_label.setText("")  # Очищаем статус
        self.status_bar.showMessage("Ожидание")  # Возвращаем статус в исходное состояние
        self.start_button.setEnabled(True)  # Включаем кнопку "Начать отслеживание"
        self.stop_button.setEnabled(False)  # Отключаем кнопку "Остановить отслеживание"

        # Скрываем прогресс на иконке в панели задач
        self.taskbar_progress.setVisible(False)
        