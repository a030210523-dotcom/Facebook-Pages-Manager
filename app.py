"""Entry point. First-run: create Super Admin (secure setup, NO default password embedded — Section 15).
Usage: python app.py            -> GUI
       python app.py --setup-admin USERNAME   -> prompts for password, creates Super Admin"""
import sys, getpass
from desktop.config import default_db_path, APP_NAME, OWNER_NAME
from desktop.database.db_manager import DBManager

def main():
    db = DBManager(default_db_path())
    if "--setup-admin" in sys.argv:
        i = sys.argv.index("--setup-admin"); username = sys.argv[i+1]
        pw = getpass.getpass("Set Super Admin password: ")
        db.create_user(username, pw, role="Super Admin")
        print(f"Super Admin '{username}' created for owner {OWNER_NAME}."); return
    if not db.has_super_admin():
        print("First run: no Super Admin yet. Create one with:  python app.py --setup-admin your_username")
    from PySide6.QtWidgets import QApplication
    from desktop.ui.main_window import MainWindow
    from desktop.ui import theme
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.STYLESHEET)
    app.setWindowIcon(theme.logo_icon())
    win = MainWindow(db); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
