import os
import winreg
import string
import json
from PyQt5.QtWidgets import QMessageBox


def find_epic_games_path():
    """Поиск пути к Epic Games Store на всех доступных дисках."""
    standard_paths = [
        os.path.join(os.environ["ProgramFiles"], "Epic Games"),
        os.path.join(os.environ["ProgramFiles(x86)"], "Epic Games"),
    ]

    for path in standard_paths:
        launcher_path = os.path.join(path, "Launcher", "Portal", "Binaries", "Win32", "EpicGamesLauncher.exe")
        if os.path.exists(launcher_path):
            return os.path.dirname(launcher_path)

    try:
        reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Epic Games\EpicGamesLauncher")
        install_location = winreg.QueryValueEx(reg_key, "AppDataPath")[0]
        if os.path.exists(os.path.join(install_location, "EpicGamesLauncher.exe")):
            return install_location
    except FileNotFoundError:
        pass

    for drive in string.ascii_uppercase:
        drive_path = f"{drive}:\\"
        if os.path.exists(drive_path):
            for root, dirs, files in os.walk(drive_path):
                if "EpicGamesLauncher.exe" in files:
                    return root

    return None

def get_installed_games():
    """Собирает информацию об установленных играх из манифестов Epic Games Launcher."""
    manifests_path = "C:\\ProgramData\\Epic\\EpicGamesLauncher\\Data\\Manifests"

    if not os.path.exists(manifests_path):
        return [], []

    manifest_files = [f for f in os.listdir(manifests_path) if f.endswith(".item")]

    if not manifest_files:
        return [], []

    installed_games = []
    invalid_path_games = []

    for filename in manifest_files:
        file_path = os.path.join(manifests_path, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
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
            continue

    return installed_games, invalid_path_games

def show_games_info(installed_games, invalid_path_games):
    """Формирует строку с информацией об играх и выводит её в QMessageBox."""
    games_info = ""
    if installed_games:
        games_info += "Установленные игры:\n"
        for game in installed_games:
            games_info += f"Игра: {game['name']}, Путь: {game['path']}\n"
    
    if invalid_path_games:
        games_info += "\nИгры с недействительными путями:\n"
        for game in invalid_path_games:
            games_info += f"Игра: {game['name']}, Путь: {game['path']} (недействителен)\n"

    if not installed_games and not invalid_path_games:
        games_info = "Игры не найдены."

    msg_box = QMessageBox()
    msg_box.setWindowTitle("Установленные игры")
    msg_box.setText(games_info)
    msg_box.exec_()

def get_unique_game_paths(installed_games):
    """Возвращает список уникальных путей к папкам с играми."""
    return list(set(os.path.dirname(game["path"]) for game in installed_games))
