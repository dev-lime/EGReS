#pyinstaller --onefile --windowed --icon=icon.ico --name="EGReS" main.py
import sys
from PyQt5.QtWidgets import QApplication
from ui import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
    