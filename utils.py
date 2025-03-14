import os
import winreg
import string
import json
from collections import defaultdict
from PyQt5.QtWidgets import QApplication, QMessageBox
import logging


def find_epic_games_path():
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

def get_installed_games():
    """
    Собирает информацию об установленных играх из манифестов Epic Games Launcher.
    Возвращает список словарей с данными об играх.
    """
    logging.basicConfig(level=logging.DEBUG)
    # Путь к папке с манифестами
    manifests_path = "C:\\ProgramData\\Epic\\EpicGamesLauncher\\Data\\Manifests"

    # Проверка существования папки с манифестами
    if not os.path.exists(manifests_path):
        logging.error("Папка с манифестами не найдена. Возможно, Epic Games Launcher не установлен.")
        return [], []  # Возвращаем два пустых списка

    # Получаем список файлов манифестов
    manifest_files = [f for f in os.listdir(manifests_path) if f.endswith(".item")]

    # Если файлов манифестов нет
    if not manifest_files:
        logging.info("Игры не установлены через Epic Games Launcher.")
        return [], []  # Возвращаем два пустых списка

    # Список для хранения информации об играх
    installed_games = []
    invalid_path_games = []

    # Проход по всем файлам манифестов
    for filename in manifest_files:
        file_path = os.path.join(manifests_path, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                # Извлечение названия игры и пути установки
                game_name = data.get("DisplayName")
                install_location = data.get("InstallLocation")
                
                if game_name and install_location:
                    if os.path.exists(install_location):
                        installed_games.append({
                            "name": game_name,
                            "path": install_location
                        })
                    else:
                        invalid_path_games.append({
                            "name": game_name,
                            "path": install_location
                        })
        except Exception as e:
            logging.error(f"Ошибка при чтении файла {filename}: {e}")

    return installed_games, invalid_path_games

def show_games_info(installed_games, invalid_path_games):
    """
    Формирует строку с информацией об играх и выводит её в QMessageBox.
    """
    # Формируем строку с информацией об играх
    games_info = ""
    if installed_games:
        games_info += "Установленные игры:\n"
        for game in installed_games:
            games_info += f"Игра: {game['name']}, Путь: {game['path']}\n"
    
    if invalid_path_games:
        games_info += "\nИгры с недействительными путями:\n"
        for game in invalid_path_games:
            games_info += f"Игра: {game['name']}, Путь: {game['path']} (недействителен)\n"

    # Если ни одной игры не найдено
    if not installed_games and not invalid_path_games:
        games_info = "Игры не найдены."

    # Выводим информацию в QMessageBox
    msg_box = QMessageBox()
    msg_box.setWindowTitle("Установленные игры")
    msg_box.setText(games_info)
    msg_box.exec_()

def get_unique_game_paths(installed_games):
    """
    Возвращает список уникальных путей к папкам с играми.
    """
    unique_game_paths = list(set(os.path.dirname(game["path"]) for game in installed_games))
    return unique_game_paths
