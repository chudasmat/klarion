import sys
import json
import os
import uuid
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QSlider, QTextEdit, 
                               QSizeGrip, QFrame, QLabel, QScrollArea)
from PySide6.QtCore import Qt, QPoint, QSize, QPropertyAnimation, QEasingCurve, Signal, QObject
from PySide6.QtGui import QColor, QIcon, QFont, QCursor
import shutil

class NoteManager(QObject):
    """Singleton-like manager for shared state across windows."""
    notes_updated = Signal() # Emitted when list changes (add/delete)
    note_content_changed = Signal(str, str) # note_id, new_content
    settings_changed = Signal() # Emitted when global settings change (theme, pin, opacity)

    def __init__(self):
        super().__init__()
        self.app_data_dir = os.path.join(os.getenv('LOCALAPPDATA'), 'Klarion')
        os.makedirs(self.app_data_dir, exist_ok=True)
        self.notes_file = os.path.join(self.app_data_dir, "notes_data.json")
        
        self.notes_data = [] 
        self.settings = {
            "pinned": False,
            "opacity": 240,
            "theme_index": 0
        }
        
        self.migrate_old_data()
        self.load_data()
        self.ensure_at_least_one_note()

    def migrate_old_data(self):
        # Migration: Check for local file
        local_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes_data.json")
        cwd_file = "notes_data.json"
        
        if not os.path.exists(self.notes_file):
            if os.path.exists(local_file):
                try:
                    shutil.move(local_file, self.notes_file)
                except Exception: pass
            elif os.path.exists(cwd_file):
                 try:
                    shutil.move(cwd_file, self.notes_file)
                 except Exception: pass

    def load_data(self):
        if os.path.exists(self.notes_file):
            try:
                with open(self.notes_file, "r") as f:
                    data = json.load(f)
                    
                    if "notes" in data:
                        self.notes_data = data.get("notes", [])
                        self.settings = data.get("settings", self.settings)
                    else:
                        # Legacy format migration
                        content = data.get("content", "")
                        note_id = str(uuid.uuid4())
                        self.notes_data = [{"id": note_id, "content": content, "timestamp": time.time()}]
                        
                        self.settings["pinned"] = data.get("pinned", False)
                        self.settings["opacity"] = data.get("opacity", 240)
                        self.settings["theme_index"] = data.get("theme_index", 0)

            except Exception as e:
                print(f"Error loading: {e}")

    def save_data(self):
        data = {
            "notes": self.notes_data,
            "settings": self.settings
        }
        try:
            with open(self.notes_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving: {e}")

    def ensure_at_least_one_note(self):
        if not self.notes_data:
            self.create_new_note(save=False)

    def create_new_note(self, save=True):
        new_id = str(uuid.uuid4())
        new_note = {"id": new_id, "content": "", "timestamp": time.time()}
        self.notes_data.insert(0, new_note)
        if save:
            self.save_data()
        self.notes_updated.emit()
        return new_id

    def delete_note(self, note_id):
        self.notes_data = [n for n in self.notes_data if n["id"] != note_id]
        if not self.notes_data:
            self.create_new_note(save=False)
        self.save_data()
        self.notes_updated.emit()

    def update_note_content(self, note_id, content):
        for note in self.notes_data:
            if note["id"] == note_id:
                note["content"] = content
                note["timestamp"] = time.time()
                break
        self.save_data()
        self.note_content_changed.emit(note_id, content)

    def get_note_content(self, note_id):
        note = next((n for n in self.notes_data if n["id"] == note_id), None)
        return note["content"] if note else ""

    def update_setting(self, key, value):
        self.settings[key] = value
        self.save_data()
        self.settings_changed.emit()

class NoteItemWidget(QFrame):
    """A single row in the side menu representing a note."""
    clicked = Signal(str) # note_id
    delete_clicked = Signal(str) # note_id
    popout_clicked = Signal(str) # note_id

    def __init__(self, note_id, content, is_active):
        super().__init__()
        self.note_id = note_id
        self.setFixedHeight(50)
        self.setCursor(Qt.PointingHandCursor)
        
        # Style based on active state
        bg_style = "background-color: rgba(255, 255, 255, 0.1); border-radius: 5px;" if is_active else ""
        self.setStyleSheet(f"NoteItemWidget {{ {bg_style} }}")

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)
        
        # Preview Text
        preview = content.strip().split('\n')[0][:20]
        if not preview: preview = "New Note"
        
        self.lbl = QLabel(preview)
        self.lbl.setStyleSheet("color: white; border: none; background: transparent;")
        self.lbl.setAttribute(Qt.WA_TransparentForMouseEvents) # Let click pass through to frame
        
        # Pop Out Button
        self.pop_btn = QPushButton("⧉")
        self.pop_btn.setFixedSize(20, 20)
        self.pop_btn.setToolTip("Open in new window")
        self.pop_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #aaa; border: none; font-size: 14px; }
            QPushButton:hover { color: #60cdff; }
        """)
        self.pop_btn.clicked.connect(self.on_popout)

        # Delete Button
        self.del_btn = QPushButton("🗑") # Trash icon
        self.del_btn.setFixedSize(20, 20)
        self.del_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #aaa; border: none; }
            QPushButton:hover { color: #ff5f57; }
        """)
        self.del_btn.clicked.connect(self.on_delete)
        
        self.layout.addWidget(self.lbl)
        self.layout.addStretch()
        self.layout.addWidget(self.pop_btn)
        self.layout.addWidget(self.del_btn)
        
        self.setObjectName("NoteItem")

    def mousePressEvent(self, event):
        self.clicked.emit(self.note_id)
        super().mousePressEvent(event)

    def on_delete(self):
        self.delete_clicked.emit(self.note_id)

    def on_popout(self):
        self.popout_clicked.emit(self.note_id)

class SideMenu(QWidget):
    """Sliding side menu."""
    def __init__(self, manager, current_note_id, note_window, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.current_note_id = current_note_id
        self.note_window = note_window # Explicit reference to controller
        
        self.setFixedWidth(0) # Initially closed
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(20, 20, 20, 0.95); border-right: 1px solid rgba(255,255,255,0.1);")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Add New Note Button
        self.add_btn = QPushButton("+ New Note")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        self.layout.addWidget(self.add_btn)
        
        # Scroll Area for notes
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 10, 0, 0)
        self.scroll_layout.addStretch() # Push items up
        
        self.scroll.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll)

    def set_current_note(self, note_id):
        self.current_note_id = note_id
        self.refresh_list()

    def refresh_list(self):
        # Clear existing items
        layout = self.scroll_layout
        while layout.count() > 1: # Keep the stretch item at end
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add items
        for note in self.manager.notes_data:
            is_active = (note["id"] == self.current_note_id)
            item = NoteItemWidget(note["id"], note["content"], is_active)
            
            # Connect signals to note_window slots
            item.clicked.connect(self.note_window.switch_note)
            item.delete_clicked.connect(self.note_window.delete_note)
            item.popout_clicked.connect(self.note_window.open_popout)
               
            layout.insertWidget(layout.count()-1, item)

class StickyNote(QMainWindow):
    THEMES = [
        {"name": "Dark", "bg": (30, 30, 30), "text": "#ffffff", "border": "rgba(255, 255, 255, 30)"},
        {"name": "Classic", "bg": (255, 247, 128), "text": "#000000", "border": "rgba(0, 0, 0, 30)"},
        {"name": "Ocean", "bg": (30, 60, 90), "text": "#ffffff", "border": "rgba(255, 255, 255, 30)"},
        {"name": "Rose", "bg": (255, 200, 200), "text": "#000000", "border": "rgba(0, 0, 0, 30)"},
        {"name": "Mint", "bg": (200, 255, 200), "text": "#000000", "border": "rgba(0, 0, 0, 30)"},
    ]

    # Keep track of active windows to prevent garbage collection
    active_windows = []

    def __init__(self, manager, note_id=None):
        super().__init__()
        self.manager = manager
        StickyNote.active_windows.append(self)

        # ID setup
        if note_id:
            self.note_id = note_id
        else:
            # Default to first available or create new
            if not self.manager.notes_data:
                self.manager.create_new_note(save=False)
            self.note_id = self.manager.notes_data[0]["id"]

        # Connect Manager Signals
        self.manager.notes_updated.connect(self.on_notes_list_updated)
        self.manager.note_content_changed.connect(self.on_external_content_change)
        self.manager.settings_changed.connect(self.on_settings_atomic_change)

        # UI Setup
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(350, 400)
        
        self.central_widget = QWidget()
        self.central_widget.setObjectName("Container")
        self.setCentralWidget(self.central_widget)
        
        self.root_layout = QHBoxLayout(self.central_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # Side Menu
        self.side_menu = SideMenu(self.manager, self.note_id, self, self)
        self.side_menu.add_btn.clicked.connect(self.create_new_note)
        self.root_layout.addWidget(self.side_menu)

        # Main Content
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.root_layout.addWidget(self.content_area)

        # Title Bar
        self.title_bar = QFrame()
        self.title_bar.setFixedHeight(40)
        self.title_bar.setObjectName("TitleBar")
        self.header_layout = QHBoxLayout(self.title_bar)
        self.header_layout.setContentsMargins(5, 0, 5, 0)

        self.menu_btn = QPushButton("≡")
        self.menu_btn.setFixedSize(30, 30)
        self.menu_btn.clicked.connect(self.toggle_menu)
        self.menu_btn.setCursor(Qt.PointingHandCursor)

        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(30, 30)
        self.pin_btn.setCheckable(True)
        self.pin_btn.clicked.connect(self.toggle_pin)
        self.pin_btn.setCursor(Qt.PointingHandCursor)

        self.theme_btn = QPushButton("🎨")
        self.theme_btn.setFixedSize(30, 30)
        self.theme_btn.clicked.connect(self.cycle_theme)
        self.theme_btn.setCursor(Qt.PointingHandCursor)

        self.header_layout.addWidget(self.menu_btn)
        self.header_layout.addWidget(self.pin_btn)
        self.header_layout.addWidget(self.theme_btn)
        self.header_layout.addStretch()

        # Opacity Slider
        self.slider_label = QLabel("👁") # Eye icon
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(50, 255)
        self.slider.setFixedWidth(60)
        self.slider.valueChanged.connect(self.update_opacity_val)
        
        self.header_layout.addWidget(self.slider_label)
        self.header_layout.addWidget(self.slider)
        self.header_layout.addStretch()

        self.min_btn = QPushButton("─")
        self.min_btn.setFixedSize(30, 30)
        self.min_btn.clicked.connect(self.showMinimized)
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.header_layout.addWidget(self.min_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self.close) # Just close window
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.header_layout.addWidget(self.close_btn)

        self.content_layout.addWidget(self.title_bar)

        # Editor
        self.text_edit = QTextEdit()
        self.text_edit.setFrameStyle(QFrame.NoFrame)
        self.text_edit.setPlaceholderText("Type a note...")
        self.text_edit.setObjectName("Content")
        self.text_edit.textChanged.connect(self.on_text_changed)
        self.content_layout.addWidget(self.text_edit)

        # Resize Grip
        self.bottom_bar = QFrame()
        self.bottom_bar.setFixedHeight(20)
        self.bottom_bar.setObjectName("BottomBar") 
        self.bottom_layout = QHBoxLayout(self.bottom_bar)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_layout.addStretch()
        self.grip = QSizeGrip(self.content_area)
        self.grip.setFixedSize(20, 20)
        self.bottom_layout.addWidget(self.grip)
        self.content_layout.addWidget(self.bottom_bar)

        # Menu Animation
        self.menu_animation = QPropertyAnimation(self.side_menu, b"maximumWidth")
        self.menu_animation.setDuration(300)
        self.menu_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.menu_open = False

        self.old_pos = None

        # Apply State
        self.apply_global_settings()
        self.load_content()
        self.side_menu.refresh_list()

    def closeEvent(self, event):
        StickyNote.active_windows.remove(self)
        event.accept()

    def apply_global_settings(self):
        s = self.manager.settings
        self.pin_btn.setChecked(s["pinned"])
        self.setWindowFlag(Qt.WindowStaysOnTopHint, s["pinned"])
        
        # Opacity
        val = s["opacity"]
        self.slider.blockSignals(True)
        self.slider.setValue(val)
        self.slider.blockSignals(False)
        self.update_style(val, s["theme_index"])
        
        # Re-show if changing flags hides it (sometimes happens with stay-on-top)
        if self.isVisible():
            self.show()

    def on_settings_atomic_change(self):
        # Called when another window changes settings
        self.apply_global_settings()

    def load_content(self):
        content = self.manager.get_note_content(self.note_id)
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(content)
        self.text_edit.blockSignals(False)

    def on_text_changed(self):
        content = self.text_edit.toPlainText()
        self.manager.update_note_content(self.note_id, content)

    def on_external_content_change(self, note_id, content):
        if note_id == self.note_id:
            if self.text_edit.toPlainText() != content:
                cursor = self.text_edit.textCursor()
                self.text_edit.blockSignals(True)
                self.text_edit.setPlainText(content)
                self.text_edit.setTextCursor(cursor)
                self.text_edit.blockSignals(False)

    def on_notes_list_updated(self):
        # Refresh menu
        self.side_menu.refresh_list()
        
        # Check if our note still exists
        exists = any(n["id"] == self.note_id for n in self.manager.notes_data)
        if not exists:
            # If deleted externally, switch to first available or close? 
            # Behavior: switch to first available
            if self.manager.notes_data:
                self.switch_note(self.manager.notes_data[0]["id"])
            else:
                # Should have been recreated by manager, but just in case
                self.close()

    def create_new_note(self):
        new_id = self.manager.create_new_note()
        self.switch_note(new_id)

    def switch_note(self, note_id):
        if note_id == self.note_id: return
        self.note_id = note_id
        self.load_content()
        self.side_menu.set_current_note(note_id)

    def delete_note(self, note_id):
        self.manager.delete_note(note_id)

    def open_popout(self, note_id):
        new_window = StickyNote(self.manager, note_id)
        new_window.show()
        # It's added to StickyNote.active_windows in __init__, so it stays alive.

    def toggle_menu(self):
        start_w = self.side_menu.width()
        end_w = 150 if start_w == 0 else 0
        self.menu_animation.setStartValue(start_w)
        self.menu_animation.setEndValue(end_w)
        self.menu_animation.start()
        self.menu_open = (end_w != 0)
        if self.menu_open:
            self.side_menu.refresh_list()

    def toggle_pin(self):
        new_state = self.pin_btn.isChecked()
        self.manager.update_setting("pinned", new_state)

    def cycle_theme(self):
        new_idx = (self.manager.settings["theme_index"] + 1) % len(self.THEMES)
        self.manager.update_setting("theme_index", new_idx)

    def update_opacity_val(self, value):
        self.manager.update_setting("opacity", value)

    def update_style(self, opacity_val, theme_idx):
        # Curve logic
        t = (opacity_val - 50) / 205.0
        if t < 0: t = 0
        curve_t = t ** 0.4 
        new_alpha = 50 + (205 * curve_t)
        bg_alpha = int(new_alpha)

        theme = self.THEMES[theme_idx]
        bg_rgb = theme["bg"]
        text_color = theme["text"]
        border = theme["border"]
        
        style = f"""
            QWidget#Container {{
                background-color: rgba({bg_rgb[0]}, {bg_rgb[1]}, {bg_rgb[2]}, {bg_alpha});
                border-radius: 10px;
                border: 1px solid {border};
            }}
            QFrame#TitleBar, QFrame#BottomBar {{ background: transparent; }}
            QTextEdit#Content {{
                background-color: transparent;
                color: {text_color};
                font-family: 'Segoe UI', sans-serif;
                font-size: 16px;
                selection-background-color: #60cdff;
                padding: 10px;
            }}
            QPushButton {{
                background-color: transparent; border: none; color: {text_color};
                font-size: 16px; border-radius: 5px; opacity: 0.8;
            }}
            QPushButton:hover {{ background-color: rgba(255, 255, 255, 40); }}
            QPushButton#CloseBtn:hover {{ background-color: #e81123; color: white; }}
            QSlider::groove:horizontal {{
                border: 1px solid rgba(100,100,100,0.5); height: 4px; 
                background: rgba(100,100,100,0.3); border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {text_color}; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px;
            }}
            QLabel {{ color: {text_color}; }}
        """
        self.setStyleSheet(style)

    # Drag Logic
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event):
        self.old_pos = None

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    import ctypes
    myappid = 'chudasmat.klarion.sticky.v1' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    app.setApplicationName("klarion")
    
    # IMPORTANT: Keep app alive until last window closes
    app.setQuitOnLastWindowClosed(True) 
    
    icon_path = resource_path("klarion.ico")
    app.setWindowIcon(QIcon(icon_path))
    
    manager = NoteManager()
    
    # Create initial window
    window = StickyNote(manager)
    window.setWindowIcon(QIcon(icon_path))
    window.setWindowTitle("klarion")
    window.show()
    
    sys.exit(app.exec())
