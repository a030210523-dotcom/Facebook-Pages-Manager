import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_main_window_builds_and_dashboard_refreshes(tmp_path):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from desktop.database.db_manager import DBManager
    from desktop.ui.main_window import MainWindow
    db = DBManager(str(tmp_path / "gui.db"))
    db.add_profile("GUI User", connection_status="Connected")
    db.add_page("42", "GUI Page")
    win = MainWindow(db)
    win._refresh_dashboard()
    assert win._dash_labels["total_pages"].text().endswith("1")
    assert win.nav.count() == 10 and win.stack.count() == 10
    win._refresh_profiles(); assert win.prof_table.rowCount() == 1
    win._refresh_pages(); assert win.page_table.rowCount() == 1
    win._refresh_health(); assert win.health_table.rowCount() == 1
    win._refresh_monet(); assert win.monet_table.rowCount() == 1
    win.close(); db.close()
