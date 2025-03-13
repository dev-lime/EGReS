import os
import winreg
import string


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
