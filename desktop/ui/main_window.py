"""PySide6 main window — Dashboard, Profiles, Pages, Health, Monetization, Reports, License, Settings, About.
All buttons are wired to real DB/service actions (Section 14). Long work runs directly on small data;
sync workers (Phase 2) will use QThread — see services/sync_service stub notes in README."""
import os, threading, webbrowser
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QStackedWidget, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
    QInputDialog, QFileDialog, QFormLayout, QDialog, QDialogButtonBox, QComboBox, QFrame,
    QGridLayout, QListWidgetItem, QAbstractItemView)
from PySide6.QtCore import Qt
from .. import config
from . import theme
from ..database.db_manager import DBManager, DuplicateError
from ..services import export_service as ex
from ..services import import_backup_service as imp

COLUMN_LABELS = {
    "id": "ID", "display_name": "Name", "facebook_user_id": "Facebook ID",
    "profile_url": "Profile URL", "profile_link": "Profile Link", "email": "Email",
    "phone": "Phone", "connection_status": "Connection", "authorization_status": "Authorization",
    "last_sync_at": "Last Sync", "page_count": "Pages", "notes": "Notes",
    "facebook_page_id": "Page ID", "page_id": "Page ID", "page_name": "Page Name",
    "page": "Page", "page_url": "Page URL", "category": "Category",
    "follower_count": "Followers", "profiles": "Profiles", "manual_status": "Status",
    "data_source": "Source", "source": "Source", "last_checked_at": "Last Checked",
    "checked_at": "Checked At", "status": "Status", "created_at": "Created",
    "accepted_at": "Accepted", "access_role": "Access Role", "access_status": "Access",
    "health_status": "Health", "restriction_status": "Restriction",
    "monetization_status": "Monetization", "technical": "Technical", "policy": "Policy",
    "restriction": "Restriction", "api_status": "API Status", "eligibility": "Eligibility",
    "profile_id": "Profile", "started_at": "Started", "finished_at": "Finished",
    "result": "Result", "pages_processed": "Pages Processed", "error_message": "Error",
    "key_last4": "Key (last 4)", "license_key": "License Key", "customer_name": "Customer",
    "license_type": "Type", "max_devices": "Devices", "expires_at": "Expires",
    "username": "Username", "role": "Role", "is_active": "Active",
}

def column_label(key):
    return COLUMN_LABELS.get(key, key.replace("_", " ").title())

def fill_table(table, columns, rows):
    table.setRowCount(len(rows)); table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels([column_label(c) for c in columns])
    table.verticalHeader().setDefaultSectionSize(36)
    for i, r in enumerate(rows):
        for j, c in enumerate(columns):
            v = r.get(c); table.setItem(i, j, QTableWidgetItem("" if v is None else str(v)))
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.resizeColumnsToContents()
    if table.horizontalHeader().count(): table.horizontalHeader().setStretchLastSection(True)

class ProfileDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent); self.setWindowTitle("Facebook Profile")
        self.setWindowIcon(theme.logo_icon()); self.setMinimumWidth(430)
        self.fields = {}
        form = QFormLayout(self)
        for key, label in [("display_name","Display Name *"),("facebook_user_id","Facebook User ID"),
                           ("profile_url","Profile URL"),("email","Email (manual if unavailable)"),
                           ("phone","Phone (manual if unavailable)"),("notes","Notes")]:
            e = QLineEdit((data or {}).get(key) or ""); self.fields[key] = e; form.addRow(label, e)
        self.status = QComboBox(); self.status.addItems(["Not Connected","Connected","Error"])
        if data: self.status.setCurrentText(data.get("connection_status") or "Not Connected")
        form.addRow("Connection Status", self.status)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); form.addRow(bb)
    def values(self):
        v = {k: e.text().strip() or None for k, e in self.fields.items()}
        v["connection_status"] = self.status.currentText(); return v

class InviteDialog(QDialog):
    """Invite a profile owner by link: name + their Facebook profile link.
    The app turns this into a connect link the owner approves on Facebook itself."""
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Invite Profile by Link")
        self.setWindowIcon(theme.logo_icon()); self.setMinimumWidth(460)
        self.fields = {}
        form = QFormLayout(self)
        for key, label in [("display_name", "Person's Name"),
                           ("profile_link", "Facebook Profile Link"),
                           ("note", "Note (optional)")]:
            e = QLineEdit(); self.fields[key] = e; form.addRow(label, e)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); form.addRow(bb)
    def values(self):
        return {k: e.text().strip() or None for k, e in self.fields.items()}

class ProfileDetailsDialog(QDialog):
    """Everything about the selected profile in one view: its info, summary
    counts, and every Page it manages with role / health / monetization."""
    def __init__(self, parent, details):
        super().__init__(parent)
        self.setWindowTitle(f"Profile Details — {details.get('display_name', '')}")
        self.setWindowIcon(theme.logo_icon()); self.setMinimumSize(760, 520)
        v = QVBoxLayout(self)
        s = details["summary"]
        info = QFormLayout()
        for key, label in [("display_name", "Name"), ("facebook_user_id", "Facebook ID"),
                           ("profile_url", "Profile URL"), ("email", "Email"),
                           ("phone", "Phone"), ("connection_status", "Connection"),
                           ("authorization_status", "Authorization"),
                           ("last_sync_at", "Last Sync"), ("notes", "Notes")]:
            info.addRow(label, QLabel(str(details.get(key) or "—")))
        v.addLayout(info)
        v.addWidget(QLabel(f"<b>{s['page_count']} Pages</b> &nbsp;•&nbsp; "
                           f"<b>{s['total_followers']:,}</b> total followers &nbsp;•&nbsp; "
                           f"<b>{s['healthy_pages']}</b> healthy &nbsp;•&nbsp; "
                           f"<b>{s['restricted_pages']}</b> restricted &nbsp;•&nbsp; "
                           f"<b>{s['needs_check_pages']}</b> need a check"))
        table = QTableWidget(); v.addWidget(table)
        fill_table(table, ["facebook_page_id", "page_name", "category", "follower_count",
                           "access_role", "access_status", "manual_status",
                           "health_status", "restriction_status", "monetization_status"],
                   details["pages"])
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject); bb.accepted.connect(self.accept); v.addWidget(bb)

class PageDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent); self.setWindowTitle("Facebook Page"); self.fields = {}
        self.setWindowIcon(theme.logo_icon()); self.setMinimumWidth(430)
        form = QFormLayout(self)
        for key, label in [("facebook_page_id","Page ID *"),("page_name","Page Name *"),("page_url","Page URL"),
                           ("category","Category"),("follower_count","Followers"),("notes","Notes")]:
            e = QLineEdit(str((data or {}).get(key) or "")); self.fields[key] = e; form.addRow(label, e)
        self.manual = QComboBox(); self.manual.addItems(["Unknown","Active","Missing - Verify","Archived"])
        if data: self.manual.setCurrentText(data.get("manual_status") or "Unknown")
        form.addRow("Manual Status", self.manual)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); form.addRow(bb)
    def values(self):
        v = {k: e.text().strip() or None for k, e in self.fields.items()}
        v["manual_status"] = self.manual.currentText()
        v["follower_count"] = int(v["follower_count"]) if v["follower_count"] and str(v["follower_count"]).isdigit() else None
        return v

class MainWindow(QMainWindow):
    def __init__(self, db: DBManager):
        super().__init__(); self.db = db
        self.setWindowTitle(f"{config.APP_NAME} — Owner: {config.OWNER_NAME}")
        self.setWindowIcon(theme.logo_icon())
        self.setStyleSheet(theme.STYLESHEET)
        self.resize(1280, 780)
        central = QWidget(); self.setCentralWidget(central)
        layout = QHBoxLayout(central); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        # ---- Sidebar (brand + navigation) ----
        sidebar = QWidget(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(238)
        sv = QVBoxLayout(sidebar); sv.setContentsMargins(0, 0, 0, 0); sv.setSpacing(0)
        brand = QWidget(); bh = QHBoxLayout(brand); bh.setContentsMargins(16, 16, 12, 12); bh.setSpacing(10)
        logo = QLabel(); logo.setPixmap(theme.logo_pixmap(38)); bh.addWidget(logo)
        bt = QVBoxLayout(); bt.setSpacing(0)
        bn = QLabel("Facebook Pages\nManager"); bn.setObjectName("BrandName"); bt.addWidget(bn)
        bs = QLabel("Professional Edition"); bs.setObjectName("BrandSub"); bt.addWidget(bs)
        bh.addLayout(bt); bh.addStretch(1); sv.addWidget(brand)
        self.nav = QListWidget(); self.nav.setObjectName("Nav")
        for text, kind in [("Dashboard","grid"),("Facebook Profiles","person"),("All Pages","flag"),
                           ("Page Health","pulse"),("Monetization","money"),("Synchronization Logs","sync"),
                           ("Reports and Exports","chart"),("License Management","key"),
                           ("Settings","gear"),("About and Support","info")]:
            self.nav.addItem(QListWidgetItem(theme.icon(kind), text))
        sv.addWidget(self.nav, 1)
        foot = QLabel(f"{config.OWNER_NAME} — {config.OWNER_ROLE}\n{config.OWNER_EMAIL}")
        foot.setObjectName("SidebarFoot"); foot.setWordWrap(True); sv.addWidget(foot)
        layout.addWidget(sidebar)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.statusBar().showMessage(
            f"{config.APP_NAME} v{config.APP_VERSION}   •   Owner: {config.OWNER_NAME} ({config.OWNER_ROLE})"
            f"   •   {config.OWNER_EMAIL}   •   {config.OWNER_PHONE}")
        self.pages_builders = [self._dashboard, self._profiles, self._pages_view, self._health,
                               self._monetization, self._sync_logs, self._reports, self._license, self._settings, self._about]
        for b in self.pages_builders: self.stack.addWidget(b())
        self.nav.currentRowChanged.connect(self._on_nav); self.nav.setCurrentRow(0)

    def _on_nav(self, i):
        self.stack.setCurrentIndex(i)
        w = self.stack.widget(i)
        if hasattr(w, "refresh"): w.refresh()

    def _page(self, title, subtitle="", kind="grid"):
        w = QWidget(); v = QVBoxLayout(w)
        v.setContentsMargins(22, 18, 22, 18); v.setSpacing(12)
        head = QHBoxLayout(); head.setSpacing(12)
        chip = QLabel(); chip.setPixmap(theme.chip(kind, theme.BLUE, 44)); chip.setFixedSize(44, 44)
        head.addWidget(chip)
        hv = QVBoxLayout(); hv.setSpacing(1)
        t = QLabel(title); t.setObjectName("PageTitle"); t.setWordWrap(True); hv.addWidget(t)
        if subtitle:
            s = QLabel(subtitle); s.setObjectName("PageSub"); s.setWordWrap(True); hv.addWidget(s)
        head.addLayout(hv, 1)
        v.addLayout(head)
        return w, v

    def _btn(self, text, fn, kind=None, primary=False, danger=False):
        b = QPushButton(theme.icon(kind, "#FFFFFF" if primary else "#1877F2"), text) if kind else QPushButton(text)
        b.clicked.connect(fn)
        if primary: b.setObjectName("Primary")
        if danger: b.setObjectName("Danger")
        return b

    def _chips(self, v, defs):
        """Small summary stat chips row. defs: [(key, title, color)] -> {key: value QLabel}"""
        row = QHBoxLayout(); row.setSpacing(10)
        values = {}
        for key, title, color in defs:
            card = QFrame(); card.setObjectName("Card")
            ch = QHBoxLayout(card); ch.setContentsMargins(12, 8, 12, 8); ch.setSpacing(9)
            dot = QLabel(); dot.setPixmap(theme.chip("grid", color, 12)); ch.addWidget(dot)
            val = QLabel("0"); val.setObjectName("MiniValue"); ch.addWidget(val)
            cap = QLabel(title); cap.setObjectName("MiniTitle"); ch.addWidget(cap)
            ch.addStretch(1); row.addWidget(card, 1)
            values[key] = val
        v.addLayout(row)
        return values

    def _empty_note(self, v, text):
        card = QFrame(); card.setObjectName("EmptyCard")
        cv = QVBoxLayout(card); cv.setContentsMargins(16, 13, 16, 13)
        lab = QLabel(text); lab.setObjectName("EmptyText"); lab.setWordWrap(True)
        lab.setAlignment(Qt.AlignCenter); cv.addWidget(lab)
        v.addWidget(card)
        return card

    # ---- Dashboard ----
    def _dashboard(self):
        w, v = self._page("Dashboard", "Overview of all your Pages, profiles and activity", "grid"); w.refresh_labels = {}
        welcome = QFrame(); welcome.setObjectName("Welcome")
        wh = QHBoxLayout(welcome); wh.setContentsMargins(18, 14, 18, 14); wh.setSpacing(12)
        wt = QVBoxLayout(); wt.setSpacing(2)
        t1 = QLabel(f"Welcome, {config.OWNER_NAME}"); t1.setObjectName("WelcomeTitle"); wt.addWidget(t1)
        t2 = QLabel("Your Facebook Pages overview — profiles, page health, monetization and sync status at a glance.")
        t2.setObjectName("WelcomeSub"); t2.setWordWrap(True); wt.addWidget(t2)
        wh.addLayout(wt, 1)
        btn = QPushButton(theme.icon("sync", "#FFFFFF"), "Refresh Dashboard"); btn.setObjectName("Primary")
        btn.clicked.connect(lambda: self._refresh_dashboard()); wh.addWidget(btn)
        v.addWidget(welcome)
        grid = QGridLayout(); grid.setSpacing(12)
        self._dash_labels = {}
        cards = [("total_profiles","Total Profiles","person","#1877F2"),
                 ("connected_profiles","Connected Profiles","link","#22A06B"),
                 ("total_pages","Total Pages","flag","#7C5CFC"),
                 ("healthy_pages","Healthy Pages","pulse","#16A34A"),
                 ("warning_pages","Warning Pages","pulse","#F59E0B"),
                 ("restricted_pages","Restricted Pages","flag","#EF4444"),
                 ("manual_verification_pages","Manual Verification Required","info","#F97316"),
                 ("monetization_known","Monetization Known","money","#0EA5A4"),
                 ("monetization_unknown","Monetization Unknown","money","#64748B"),
                 ("sync_failures","Sync Failures","sync","#DC2626")]
        for i, (key, title, kind, color) in enumerate(cards):
            card = QFrame(); card.setObjectName("Card")
            ch = QHBoxLayout(card); ch.setContentsMargins(13, 11, 13, 11); ch.setSpacing(11)
            chip = QLabel(); chip.setPixmap(theme.chip(kind, color)); ch.addWidget(chip)
            cv = QVBoxLayout(); cv.setSpacing(0)
            val = QLabel("0"); val.setObjectName("CardValue"); cv.addWidget(val)
            cap = QLabel(title); cap.setObjectName("CardTitle"); cap.setWordWrap(True); cv.addWidget(cap)
            ch.addLayout(cv, 1)
            grid.addWidget(card, i // 5, i % 5)
            self._dash_labels[key] = val
        v.addLayout(grid)
        qa = QFrame(); qa.setObjectName("Card")
        qh = QHBoxLayout(qa); qh.setContentsMargins(16, 12, 16, 12); qh.setSpacing(10)
        ql = QLabel("Quick Actions"); ql.setObjectName("SectionLabel"); qh.addWidget(ql); qh.addStretch(1)
        qh.addWidget(self._btn("Add Profile", lambda: (self.nav.setCurrentRow(1), self._add_profile()), "plus"))
        qh.addWidget(self._btn("Connect Facebook", lambda: (self.nav.setCurrentRow(1), self._connect_facebook()), "link", primary=True))
        qh.addWidget(self._btn("Sync Pages", lambda: (self.nav.setCurrentRow(1), self._sync_selected_profile()), "sync"))
        qh.addWidget(self._btn("Export Pages CSV", lambda: self._export("csv"), "download"))
        v.addWidget(qa); v.addStretch(1)
        def refresh(): self._refresh_dashboard()
        w.refresh = refresh; self._dash_widget = w; return w
    def _refresh_dashboard(self):
        if not hasattr(self, "_dash_labels"): return
        s = self.db.dashboard_stats()
        for k, lab in self._dash_labels.items(): lab.setText(str(s[k]))

    # ---- Profiles ----
    def _profiles(self):
        w, v = self._page("Facebook Profiles", "Connect profiles with the official Facebook Login and sync their Pages", "person")
        self._prof_chips = self._chips(v, [("total","Total Profiles","#1877F2"),
                                           ("connected","Connected","#22A06B"),
                                           ("pages","Pages Linked","#7C5CFC")])
        self.prof_search = QLineEdit(); self.prof_search.setPlaceholderText("Search name / Facebook ID / URL")
        self.prof_search.textChanged.connect(lambda: self._refresh_profiles()); v.addWidget(self.prof_search)
        self.prof_table = QTableWidget(); v.addWidget(self.prof_table)
        self.prof_table.itemDoubleClicked.connect(lambda *_: self._view_profile_details())
        self.prof_empty = self._empty_note(v, "No profiles yet. Click  “Add Profile”  to add one manually, or  “Connect Facebook (OAuth)”  to connect with the official Facebook Login.")
        row = QHBoxLayout()
        row.addWidget(self._btn("Add Profile", self._add_profile, "plus", primary=True))
        row.addWidget(self._btn("Profile Details", self._view_profile_details, "person"))
        row.addWidget(self._btn("Edit Selected", self._edit_profile, "pencil"))
        row.addWidget(self._btn("Delete Selected", self._delete_profile, "trash", danger=True))
        row.addWidget(self._btn("Refresh", lambda: self._refresh_profiles(), "sync"))
        row.addStretch(1)
        v.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(self._btn("Connect Facebook (OAuth)", self._connect_facebook, "link", primary=True))
        row2.addWidget(self._btn("Invite Profile (Link)", self._create_invite, "person", primary=True))
        row2.addWidget(self._btn("Sync Pages (Selected Profile)", self._sync_selected_profile, "sync"))
        row2.addStretch(1)
        v.addLayout(row2)
        inv_label = QLabel("Profile Invites — send the connect link to the profile owner; "
                           "when they accept on Facebook, use “Check Invite Status” and the profile "
                           "with all its Pages is added automatically.")
        inv_label.setWordWrap(True); v.addWidget(inv_label)
        self.invite_table = QTableWidget(); v.addWidget(self.invite_table)
        irow = QHBoxLayout()
        irow.addWidget(self._btn("Copy Connect Link", self._copy_invite_link, "link"))
        irow.addWidget(self._btn("Check Invite Status", self._check_invite, "sync", primary=True))
        irow.addWidget(self._btn("Delete Invite", self._delete_invite, "trash", danger=True))
        irow.addStretch(1)
        v.addLayout(irow)
        w.refresh = lambda: self._refresh_profiles(); return w
    def _refresh_profiles(self):
        rows = self.db.list_profiles(search=self.prof_search.text() or None)
        for r in rows: r["page_count"] = self.db.profile_page_count(r["id"])
        fill_table(self.prof_table, ["id","display_name","facebook_user_id","profile_url","email","phone",
                                     "connection_status","authorization_status","last_sync_at","page_count","notes"], rows)
        if hasattr(self, "_prof_chips"):
            self._prof_chips["total"].setText(str(len(rows)))
            self._prof_chips["connected"].setText(str(sum(1 for r in rows if r.get("connection_status") == "Connected")))
            self._prof_chips["pages"].setText(str(sum(r.get("page_count", 0) for r in rows)))
        if hasattr(self, "prof_empty"): self.prof_empty.setVisible(len(rows) == 0)
        if hasattr(self, "invite_table"): self._refresh_invites()
    def _selected_id(self, table):
        r = table.currentRow()
        return int(table.item(r, 0).text()) if r >= 0 and table.item(r, 0) else None
    def _add_profile(self):
        d = ProfileDialog(self)
        if d.exec():
            try: self.db.add_profile(**{k: v for k, v in d.values().items() if k in
                        ("display_name","facebook_user_id","profile_url","email","phone","notes","connection_status")})
            except (ValueError, DuplicateError) as e: QMessageBox.warning(self, "Cannot add", str(e))
            self._refresh_profiles()
    def _view_profile_details(self):
        pid = self._selected_id(self.prof_table)
        if not pid:
            QMessageBox.information(self, "Select a profile", "Select a profile row first — "
                                    "its full details (info, Pages, health, monetization) will open here.")
            return
        details = self.db.profile_details(pid)
        if details: ProfileDetailsDialog(self, details).exec()
    def _edit_profile(self):
        pid = self._selected_id(self.prof_table)
        if not pid: return
        cur = [p for p in self.db.list_profiles() if p["id"] == pid][0]
        d = ProfileDialog(self, cur)
        if d.exec(): self.db.update_profile(pid, **d.values()); self._refresh_profiles()
    def _delete_profile(self):
        pid = self._selected_id(self.prof_table)
        if pid and QMessageBox.question(self, "Confirm", "Delete this profile and its Page links?") == QMessageBox.Yes:
            self.db.delete_profile(pid); self._refresh_profiles()

    # ---- Profile invites (connect by link) ----
    def _refresh_invites(self):
        rows = self.db.list_invites()
        fill_table(self.invite_table, ["id", "display_name", "profile_link", "status",
                                       "created_at", "accepted_at"], rows)
    def _selected_invite(self):
        iid = self._selected_id(self.invite_table)
        return self.db.get_invite(iid) if iid else None
    def _create_invite(self):
        if not self._require_license(): return
        d = InviteDialog(self)
        if not d.exec(): return
        vals = d.values()
        from ..services import invite_service as inv
        invite = inv.create_invite(self.db, vals.get("display_name"),
                                   vals.get("profile_link"), vals.get("note"))
        link = inv.connect_link(self._server_url(), invite["code"])
        try: inv.register_invite(self._server_url(), invite)
        except Exception: pass  # registration is retried automatically on status check
        self._refresh_invites()
        box = QMessageBox(self); box.setWindowTitle("Invite created — send this link")
        box.setText("Send this connect link to the profile owner (Messenger / WhatsApp / email).\n\n"
                    "When they open it, Facebook's official login opens; they log in and accept "
                    "the permissions. Then click “Check Invite Status” here — the profile and all "
                    "its Pages will be added automatically with their details.")
        link_edit = QLineEdit(link); link_edit.setReadOnly(True)
        box.layout().addWidget(link_edit, 1, 0, 1, 2)
        copy_btn = box.addButton("Copy Link", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if box.clickedButton() is copy_btn:
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(link)
    def _copy_invite_link(self):
        invite = self._selected_invite()
        if not invite: QMessageBox.information(self, "Select an invite", "Select an invite row first."); return
        from ..services.invite_service import connect_link
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(connect_link(self._server_url(), invite["code"]))
        QMessageBox.information(self, "Copied", "Connect link copied. Send it to the profile owner.")
    def _check_invite(self):
        if not self._require_license(): return
        invite = self._selected_invite()
        if not invite: QMessageBox.information(self, "Select an invite", "Select an invite row first."); return
        from ..services import invite_service as inv
        outcome = {}
        def work():
            outcome.update(inv.check_invite(self.db, self._server_url(), invite["id"],
                                            token_store=self._token_store()))
        th = threading.Thread(target=work, daemon=True); th.start()
        def done():
            if th.is_alive(): QTimer.singleShot(700, done); return
            st = outcome.get("status")
            if st == "Connected":
                QMessageBox.information(self, "Profile connected",
                    f"The profile was accepted and added automatically — "
                    f"{outcome.get('pages_imported', 0)} Page(s) imported with their details.")
            elif st == "Pending":
                QMessageBox.information(self, "Not accepted yet",
                    "The profile owner has not accepted the invite yet. Ask them to open the "
                    "connect link and complete the Facebook login, then check again.")
            else:
                QMessageBox.warning(self, "Invite check failed",
                    f"{outcome.get('error', 'Unknown error')}\n\nMake sure the licensing server is "
                    "running and reachable (Settings shows its URL).")
            self._refresh_profiles()
        QTimer.singleShot(700, done)
    def _delete_invite(self):
        invite = self._selected_invite()
        if invite and QMessageBox.question(self, "Confirm", "Delete this invite?") == QMessageBox.Yes:
            self.db.delete_invite(invite["id"]); self._refresh_invites()

    def _require_license(self):
        st = self.license_status()
        if not st.get("licensed"):
            QMessageBox.warning(self, "License required",
                f"{st.get('message','This feature needs an active license.')}\n\n"
                "Go to License Management to activate. Your local data is safe and is NOT deleted.")
            return False
        return True

    # ---- Meta OAuth + Sync (Phase 2) ----
    def _token_store(self):
        from ..services.token_store import TokenStore
        from ..config import app_data_dir
        d = app_data_dir()
        return TokenStore(os.path.join(d, "tokens.enc"), os.path.join(d, "tokens.key"))
    def _connect_facebook(self):
        if not self._require_license(): return
        from ..services import oauth_service as oauth
        app_id = config.META_APP_ID or self.db.get_setting("meta_app_id")
        if not app_id:
            app_id, ok = QInputDialog.getText(self, "Meta App ID",
                "Enter your Meta App ID (from developers.facebook.com):")
            if not ok or not app_id: return
            self.db.set_setting("meta_app_id", app_id.strip()); app_id = app_id.strip()
        server, result, redirect_uri = oauth.start_callback_server()
        url, state = oauth.build_oauth_url(app_id, redirect_uri, config.META_API_VERSION)
        webbrowser.open(url)
        QMessageBox.information(self, "Facebook Login opened",
            "Complete the official Facebook Login in your browser. The app is waiting for the redirect on this PC.\n"
            "The app never asks for your Facebook password.")
        threading.Thread(target=server.handle_request, daemon=True).start()
        def poll():
            if result.code or result.error:
                server.server_close()
                if result.error: QMessageBox.warning(self, "Authorization failed", str(result.error)); return
                if not oauth.verify_state(result.state, state):
                    QMessageBox.warning(self, "Security check", "OAuth state mismatch — login discarded."); return
                try:
                    data = oauth.exchange_code_via_server(self._server_url(), result.code, redirect_uri)
                except Exception as e:
                    QMessageBox.warning(self, "Token exchange failed",
                        f"{e}\n\nThe exchange is done by the licensing server, which holds the Meta App Secret. "
                        "Make sure the server is running and META_APP_ID/META_APP_SECRET are set on the server."); return
                token = data["access_token"]
                from ..services.meta_api import MetaAPIClient
                try: me = MetaAPIClient(token, config.META_API_VERSION).get_me()
                except Exception as e: QMessageBox.warning(self, "Connected but profile fetch failed", str(e)); return
                existing = [p for p in self.db.list_profiles() if p.get("facebook_user_id") == str(me["id"])]
                pid = existing[0]["id"] if existing else self.db.add_profile(
                    me.get("name") or "Facebook User", facebook_user_id=str(me["id"]),
                    connection_status="Connected")
                self.db.update_profile(pid, connection_status="Connected", authorization_status="Authorized")
                self._token_store().set_token(f"profile:{pid}", token, kind="user")
                QMessageBox.information(self, "Connected",
                    f"Connected as {me.get('name')}. Token stored encrypted (masked: "
                    f"{self._token_store().mask(token)}). Use 'Sync Pages' to discover Pages.")
                self._refresh_profiles()
            else:
                QTimer.singleShot(700, poll)
        QTimer.singleShot(700, poll)
    def _sync_selected_profile(self):
        if not self._require_license(): return
        pid = self._selected_id(self.prof_table)
        if not pid: QMessageBox.information(self, "Select a profile", "Select a connected profile first."); return
        token = self._token_store().get_token(f"profile:{pid}")
        if not token:
            QMessageBox.warning(self, "Not connected", "No stored token for this profile. Use 'Connect Facebook (OAuth)' first."); return
        from ..services.meta_api import MetaAPIClient
        from ..services.sync_service import sync_profile_pages
        client = MetaAPIClient(token, config.META_API_VERSION)
        outcome = {}
        def work(): outcome.update(sync_profile_pages(self.db, pid, client, token_store=self._token_store()))
        th = threading.Thread(target=work, daemon=True); th.start()
        def done():
            if th.is_alive(): QTimer.singleShot(700, done); return
            if outcome.get("ok"):
                QMessageBox.information(self, "Sync finished",
                    f"Result: {outcome['result']} — Pages processed: {outcome['pages_processed']}, "
                    f"missing flagged: {len(outcome.get('missing_flagged', []))}")
            else:
                QMessageBox.warning(self, "Sync failed", "; ".join(outcome.get("errors", ["unknown error"])))
            self._refresh_profiles()
        QTimer.singleShot(700, done)

    # ---- Pages ----
    def _pages_view(self):
        w, v = self._page("All Pages", "Every Facebook Page you manage — add, edit, open and track them here", "flag")
        self._page_chips = self._chips(v, [("total","Total Pages","#7C5CFC"),
                                           ("missing","Missing - Verify","#F97316"),
                                           ("followers","Total Followers","#1877F2")])
        self.page_search = QLineEdit(); self.page_search.setPlaceholderText("Search Page name / ID / URL")
        self.page_search.textChanged.connect(lambda: self._refresh_pages()); v.addWidget(self.page_search)
        self.page_table = QTableWidget(); v.addWidget(self.page_table)
        self.page_empty = self._empty_note(v, "No Pages yet. Sync a connected profile to discover its Pages automatically, or click  “Add Page”  to add one manually.")
        row = QHBoxLayout()
        row.addWidget(self._btn("Add Page", self._add_page, "plus", primary=True))
        row.addWidget(self._btn("Edit Selected", self._edit_page, "pencil"))
        row.addWidget(self._btn("Delete Selected", self._delete_page, "trash", danger=True))
        row.addWidget(self._btn("Open in Browser", self._open_page, "link"))
        row.addWidget(self._btn("Copy URL", self._copy_page_url, "pencil"))
        row.addWidget(self._btn("Refresh", lambda: self._refresh_pages(), "sync"))
        row.addStretch(1)
        v.addLayout(row); w.refresh = lambda: self._refresh_pages(); return w
    def _refresh_pages(self):
        rows = self.db.list_pages(search=self.page_search.text() or None)
        fill_table(self.page_table, ["id","facebook_page_id","page_name","page_url","category","follower_count",
                                     "profiles","manual_status","data_source","last_checked_at","notes"], rows)
        if hasattr(self, "_page_chips"):
            self._page_chips["total"].setText(str(len(rows)))
            self._page_chips["missing"].setText(str(sum(1 for r in rows if str(r.get("manual_status") or "").startswith("Missing"))))
            self._page_chips["followers"].setText(str(sum(r.get("follower_count") or 0 for r in rows)))
        if hasattr(self, "page_empty"): self.page_empty.setVisible(len(rows) == 0)
    def _add_page(self):
        d = PageDialog(self)
        if d.exec():
            try: self.db.add_page(**d.values())
            except (ValueError, DuplicateError) as e: QMessageBox.warning(self, "Cannot add", str(e))
            self._refresh_pages()
    def _edit_page(self):
        pgid = self._selected_id(self.page_table)
        if not pgid: return
        cur = [p for p in self.db.list_pages() if p["id"] == pgid][0]
        d = PageDialog(self, cur)
        if d.exec():
            vals = d.values(); vals.pop("facebook_page_id", None); self.db.update_page(pgid, **vals); self._refresh_pages()
    def _delete_page(self):
        pgid = self._selected_id(self.page_table)
        if pgid and QMessageBox.question(self, "Confirm", "Delete this Page record?") == QMessageBox.Yes:
            self.db.delete_page(pgid); self._refresh_pages()
    def _page_url(self):
        r = self.page_table.currentRow()
        return self.page_table.item(r, 3).text() if r >= 0 and self.page_table.item(r, 3) else None
    def _open_page(self):
        u = self._page_url()
        if u: webbrowser.open(u)
    def _copy_page_url(self):
        u = self._page_url()
        if u:
            from PySide6.QtWidgets import QApplication; QApplication.clipboard().setText(u)

    # ---- Health / Monetization / Sync ----
    def _page_client(self, page_row):
        """MetaAPIClient for a Page: Page token first, else a linked profile's user token; None if neither."""
        ts = self._token_store()
        token = ts.get_token(f"page:{page_row['id']}")
        if not token:
            for pid in self.db.page_profile_ids(page_row["id"]):
                token = ts.get_token(f"profile:{pid}")
                if token: break
        if not token: return None
        from ..services.meta_api import MetaAPIClient
        return MetaAPIClient(token, config.META_API_VERSION)
    def _health(self):
        w, v = self._page("Page Health", "Technical health is checked through the API; policy status stays Unknown until you verify it manually", "pulse")
        self._health_chips = self._chips(v, [("total","Total Pages","#1877F2"),
                                             ("healthy","Healthy","#16A34A"),
                                             ("warning","Warning","#F59E0B"),
                                             ("restricted","Restricted","#EF4444")])
        self.health_table = QTableWidget(); v.addWidget(self.health_table)
        self.health_empty = self._empty_note(v, "No Pages to check yet. Pages appear here after you add or sync them.")
        row = QHBoxLayout()
        row.addWidget(self._btn("Run Technical Check (All Pages)", self._run_health_checks, "pulse", primary=True))
        row.addWidget(self._btn("Record Manual Policy Check (Selected)", self._manual_health_dialog, "pencil"))
        row.addWidget(self._btn("Refresh", lambda: self._refresh_health(), "sync"))
        row.addStretch(1)
        v.addLayout(row)
        w.refresh = lambda: self._refresh_health(); return w
    def _run_health_checks(self):
        from ..services.health_service import check_all_pages
        summary = check_all_pages(self.db, self._page_client)
        self._refresh_health()
        QMessageBox.information(self, "Health checks done",
            "; ".join(f"{k}: {n}" for k, n in summary.items()) or "No Pages yet.")
    def _manual_health_dialog(self):
        pgid = self._selected_id(self.health_table)
        if not pgid: QMessageBox.information(self, "Select a Page", "Select a row in the health table first."); return
        from ..services.health_service import record_manual_health
        policy, ok = QInputDialog.getItem(self, "Manual policy check",
            "Policy status you verified in Meta Business Suite:", ["Healthy","Warning","Restricted","Unknown"], 0, False)
        if not ok: return
        restriction, ok = QInputDialog.getItem(self, "Restriction",
            "Restriction status you verified:", ["None Known","Restricted","Unknown"], 0, False)
        if not ok: return
        notes, _ = QInputDialog.getText(self, "Notes", "Optional notes:")
        record_manual_health(self.db, pgid, policy, restriction, notes or None)
        self._refresh_health()
    def _refresh_health(self):
        rows = []
        for p in self.db.list_pages():
            h = self.db.latest_health(p["id"])
            rows.append({"id": p["id"], "page": p["page_name"], "page_id": p["facebook_page_id"],
                         "technical": h["technical_connection_status"], "policy": h["policy_status"],
                         "restriction": h["restriction_status"], "checked_at": h["checked_at"], "source": h["data_source"]})
        fill_table(self.health_table, ["id","page","page_id","technical","policy","restriction","checked_at","source"], rows)
        if hasattr(self, "_health_chips"):
            self._health_chips["total"].setText(str(len(rows)))
            self._health_chips["healthy"].setText(str(sum(1 for r in rows if r["policy"] == "Healthy")))
            self._health_chips["warning"].setText(str(sum(1 for r in rows if r["policy"] == "Warning")))
            self._health_chips["restricted"].setText(str(sum(1 for r in rows if r["policy"] == "Restricted")))
        if hasattr(self, "health_empty"): self.health_empty.setVisible(len(rows) == 0)
    def _monetization(self):
        w, v = self._page("Monetization", "API, manual and unknown statuses are always kept separate — nothing is guessed", "money")
        self._monet_chips = self._chips(v, [("total","Total Pages","#1877F2"),
                                            ("eligible","Eligible","#16A34A"),
                                            ("verified","Manually Verified","#0EA5A4"),
                                            ("unknown","Unknown","#64748B")])
        self.monet_table = QTableWidget(); v.addWidget(self.monet_table)
        self.monet_empty = self._empty_note(v, "No Pages yet. Pages appear here after you add or sync them.")
        from ..services.monetization_service import LIMITATION_MESSAGE
        lbl = QLabel(LIMITATION_MESSAGE + " Status is never inferred from follower count.")
        lbl.setWordWrap(True); lbl.setObjectName("PageSub"); v.addWidget(lbl)
        row = QHBoxLayout()
        row.addWidget(self._btn("Record Manual Verification (Selected)", self._manual_monet_dialog, "pencil", primary=True))
        row.addWidget(self._btn("Open Official Monetization Dashboard", lambda: webbrowser.open("https://business.facebook.com/content-monetization"), "link"))
        row.addWidget(self._btn("Refresh", lambda: self._refresh_monet(), "sync"))
        row.addStretch(1)
        v.addLayout(row)
        w.refresh = lambda: self._refresh_monet(); return w
    def _manual_monet_dialog(self):
        pgid = self._selected_id(self.monet_table)
        if not pgid: QMessageBox.information(self, "Select a Page", "Select a row in the monetization table first."); return
        from ..services.monetization_service import record_manual_verification, MANUAL_STATUSES
        status, ok = QInputDialog.getItem(self, "Manual monetization verification",
            "What did you verify in the official Meta dashboard?", MANUAL_STATUSES, 0, False)
        if not ok: return
        elig = {"Manually Verified - Eligible": "Eligible", "Manually Verified - Not Eligible": "Not Eligible",
                "Manually Verified - Restricted": "Restricted"}.get(status, "Unknown")
        notes, _ = QInputDialog.getText(self, "Notes", "Optional notes:")
        record_manual_verification(self.db, pgid, status, notes or None, eligibility=elig)
        self._refresh_monet()
    def _refresh_monet(self):
        rows = []
        for p in self.db.list_pages():
            m = self.db.latest_monetization(p["id"])
            rows.append({"id": p["id"], "page": p["page_name"], "page_id": p["facebook_page_id"], "api_status": m["api_status"],
                         "eligibility": m["eligibility_status"], "manual_status": m["manual_status"],
                         "checked_at": m["checked_at"], "source": m["data_source"]})
        fill_table(self.monet_table, ["id","page","page_id","api_status","eligibility","manual_status","checked_at","source"], rows)
        if hasattr(self, "_monet_chips"):
            self._monet_chips["total"].setText(str(len(rows)))
            self._monet_chips["eligible"].setText(str(sum(1 for r in rows if r["eligibility"] == "Eligible")))
            self._monet_chips["verified"].setText(str(sum(1 for r in rows if str(r["manual_status"] or "").startswith("Manually"))))
            self._monet_chips["unknown"].setText(str(sum(1 for r in rows if r["eligibility"] == "Unknown")))
        if hasattr(self, "monet_empty"): self.monet_empty.setVisible(len(rows) == 0)
    def _sync_logs(self):
        w, v = self._page("Synchronization Logs", "History of every sync run, its result and any errors", "sync")
        self._sync_chips = self._chips(v, [("total","Total Runs","#1877F2"),
                                           ("ok","Successful","#16A34A"),
                                           ("err","With Errors","#EF4444")])
        self.sync_table = QTableWidget(); v.addWidget(self.sync_table)
        self.sync_empty = self._empty_note(v, "No sync runs yet. Connect a profile and use  “Sync Pages”  — every run will be recorded here.")
        w.refresh = lambda: self._refresh_sync_logs()
        return w
    def _refresh_sync_logs(self):
        rows = self.db.list_sync_logs()
        fill_table(self.sync_table, ["id","profile_id","started_at","finished_at","result","pages_processed","error_message"], rows)
        if hasattr(self, "_sync_chips"):
            self._sync_chips["total"].setText(str(len(rows)))
            self._sync_chips["ok"].setText(str(sum(1 for r in rows if str(r.get("result") or "").lower().startswith("success"))))
            self._sync_chips["err"].setText(str(sum(1 for r in rows if r.get("error_message"))))
        if hasattr(self, "sync_empty"): self.sync_empty.setVisible(len(rows) == 0)

    # ---- Reports ----
    def _reports(self):
        w, v = self._page("Reports and Exports", "Export professional reports, import Pages and back up your data", "chart")
        grid = QGridLayout(); grid.setSpacing(12)
        for i, (txt, fn) in enumerate([("Export Pages CSV", lambda: self._export("csv")), ("Export Pages Excel", lambda: self._export("xlsx")),
                        ("Export Pages PDF", lambda: self._export("pdf")), ("Import Pages CSV", self._import_csv),
                        ("Backup Database", self._backup), ("Restore Database", self._restore)]):
            kind = "download" if txt.startswith(("Export", "Backup")) else ("plus" if txt.startswith("Import") else "sync")
            b = QPushButton(theme.icon(kind, "#FFFFFF" if txt.startswith("Export") else "#1877F2"), txt)
            b.clicked.connect(fn); b.setMinimumHeight(46)
            if txt.startswith("Export"): b.setObjectName("Primary")
            grid.addWidget(b, i // 3, i % 3)
        v.addLayout(grid); v.addStretch(1)
        return w
    def _export(self, kind):
        cols, rows = ex.pages_dataset(self.db)
        path, _ = QFileDialog.getSaveFileName(self, "Save report", f"pages_report.{kind}")
        if not path: return
        if os.path.exists(path): QMessageBox.warning(self, "Exists", "File exists — choose another name (no silent overwrite)."); return
        try:
            if kind == "csv": ex.export_csv(rows, cols, path)
            elif kind == "xlsx": ex.export_excel({"Pages": (cols, rows), "Profiles": (ex.PROFILE_COLUMNS, self.db.list_profiles())}, path)
            else: ex.export_pdf("Facebook Pages Report", cols, rows, path, summary=f"Total Pages: {len(rows)}")
            QMessageBox.information(self, "Done", f"Exported to {path}")
        except Exception as e: QMessageBox.warning(self, "Export failed", str(e))
    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV (*.csv)")
        if not path: return
        preview = imp.preview_csv(path)
        if QMessageBox.question(self, "Import preview",
            f"Valid: {len(preview['valid'])}  Errors: {len(preview['errors'])}\n{chr(10).join(preview['errors'][:5])}\nProceed?") == QMessageBox.Yes:
            r = imp.import_pages(self.db, preview)
            QMessageBox.information(self, "Import done", f"Imported: {r['imported']}  Skipped duplicates: {len(r['skipped'])}")
    def _backup(self):
        path, _ = QFileDialog.getSaveFileName(self, "Backup database", "fpm_backup.db")
        if path:
            try: imp.backup_db(self.db.db_path, path); QMessageBox.information(self, "Done", "Backup created.")
            except Exception as e: QMessageBox.warning(self, "Backup failed", str(e))
    def _restore(self):
        path, _ = QFileDialog.getOpenFileName(self, "Restore database", "", "DB (*.db)")
        if path and QMessageBox.question(self, "Confirm restore", "This replaces current data. Continue?") == QMessageBox.Yes:
            imp.restore_db(self.db.db_path, path, confirmed=True)
            QMessageBox.information(self, "Done", "Restored. Restart the app.")

    # ---- License / Settings / About ----
    def _server_url(self):
        """Effective server URL for licensing, Meta token exchange and invites.
        With only the compiled default (https://localhost:8000) configured, probe
        the plain local owner server (http://127.0.0.1:8000) once and use it when
        it answers — activation then works even when the app was opened directly
        from the exe, without the launcher .bat. A real configured/production
        URL is always used as-is."""
        url = self.db.get_setting("license_server_url") or config.LICENSING_SERVER_URL
        if url.rstrip("/") in ("https://localhost:8000", "https://127.0.0.1:8000"):
            try:
                import requests
                if requests.get("http://127.0.0.1:8000/health", timeout=1.5).status_code == 200:
                    return "http://127.0.0.1:8000"
            except Exception:
                pass
        return url
    def _license_client(self):
        from ..services.licensing_client import LicensingClient, LicenseCache
        from ..config import app_data_dir
        d = app_data_dir()
        cache = LicenseCache(os.path.join(d, "license.enc"), os.path.join(d, "license.key"))
        return LicensingClient(self._server_url(), cache)
    def license_status(self):
        try: return self._license_client().current_status(config.OFFLINE_GRACE_DAYS)
        except Exception as e: return {"licensed": False, "status": "Unknown", "message": str(e)}
    def _license(self):
        w, v = self._page("License Management", "Activate your license key and check its status", "key")
        card = QFrame(); card.setObjectName("Card")
        cv = QVBoxLayout(card); cv.setContentsMargins(18, 14, 18, 14)
        info = QLabel(f"{config.APP_NAME}\nSoftware Owner: {config.OWNER_NAME}\n"
                      f"Owner Email: {config.OWNER_EMAIL}\nOwner Phone: {config.OWNER_PHONE}\n"
                      f"Licensing Server: {config.LICENSING_SERVER_URL}")
        info.setWordWrap(True); cv.addWidget(info); v.addWidget(card)
        self.lic_key = QLineEdit(); self.lic_key.setPlaceholderText("FPM-XXXX-XXXX-XXXX-XXXX"); v.addWidget(self.lic_key)
        scard = QFrame(); scard.setObjectName("Card")
        sv2 = QVBoxLayout(scard); sv2.setContentsMargins(18, 14, 18, 14)
        self.lic_status = QLabel(""); self.lic_status.setWordWrap(True); sv2.addWidget(self.lic_status)
        v.addWidget(scard)
        row = QHBoxLayout()
        row.addWidget(self._btn("Activate", self._activate_license, "key", primary=True))
        row.addWidget(self._btn("Validate Online", self._validate_license, "link"))
        row.addWidget(self._btn("Refresh Status", lambda: self._refresh_license(), "sync"))
        row.addStretch(1)
        v.addLayout(row)
        sup = QLabel("Support: contact the software owner (above) if activation fails, your key is "
                     "expired/suspended, or you changed computer and need a device slot freed.")
        sup.setWordWrap(True); sup.setObjectName("PageSub"); v.addWidget(sup)
        v.addStretch(1)
        w.refresh = lambda: self._refresh_license()
        return w
    def _refresh_license(self):
        st = self.license_status()
        p = st.get("payload") or {}
        extra = ""
        if p:
            extra = (f"\nCustomer: {p.get('customer_name')}  |  Type: {p.get('license_type')}  |  "
                     f"Expiry: {p.get('expiry_date') or 'Lifetime'}  |  Devices: {p.get('max_devices')}")
        self.lic_status.setText(f"Status: {st['status']}\n{st['message']}{extra}")
    def _activate_license(self):
        from ..services.licensing_client import get_or_create_installation_id
        key = self.lic_key.text().strip()
        if not key: QMessageBox.warning(self, "Missing key", "Enter a license key first."); return
        try:
            payload = self._license_client().activate(key, get_or_create_installation_id(self.db),
                                                      device_label=os.environ.get("COMPUTERNAME", "Windows PC"),
                                                      app_version=config.APP_VERSION)
            QMessageBox.information(self, "Activated",
                f"License activated for {payload.get('customer_name')} (expires: {payload.get('expiry_date') or 'Lifetime'}).")
        except Exception as e:
            QMessageBox.warning(self, "Activation failed", str(e))
        self._refresh_license()
    def _validate_license(self):
        from ..services.licensing_client import get_or_create_installation_id
        cached = self._license_client().cache.load()
        key = self.lic_key.text().strip() or (cached or {}).get("license_key")
        if not key: QMessageBox.warning(self, "No key", "Activate first or enter your license key."); return
        try:
            self._license_client().validate_online(key, get_or_create_installation_id(self.db))
            QMessageBox.information(self, "Validated", "License validated online successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Validation failed", str(e))
        self._refresh_license()
    def _info_card(self, v, text):
        card = QFrame(); card.setObjectName("Card")
        cv = QVBoxLayout(card); cv.setContentsMargins(18, 16, 18, 16)
        lab = QLabel(text); lab.setWordWrap(True); cv.addWidget(lab)
        v.addWidget(card); v.addStretch(1)
        return card
    def _settings(self):
        w, v = self._page("Settings", "Application configuration and connection details", "gear")
        self._info_card(v, f"Meta API Version: {config.META_API_VERSION}\nMeta App ID: {config.META_APP_ID or '(not configured — Phase 2)'}\n"
                           f"Licensing Server: {config.LICENSING_SERVER_URL}\nOffline Grace: {config.OFFLINE_GRACE_DAYS} days\n"
                           "App Secrets / signing keys are NEVER shown or stored here.")
        return w
    def _about(self):
        w, v = self._page("About and Support", "Software, owner and support information", "info")
        self._info_card(v, f"{config.APP_NAME} v{config.APP_VERSION}\n\nOwner: {config.OWNER_NAME} ({config.OWNER_ROLE})\n"
                           f"Email: {config.OWNER_EMAIL}\nPhone: {config.OWNER_PHONE}\n\n"
                           "Manages only Pages you are authorized to access via the official Meta Graph API. "
                           "Facebook passwords are never asked for or stored.")
        return w
