import sys
import json
import os
import uuid
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QSlider, QTextEdit, 
                               QSizeGrip, QFrame, QLabel, QScrollArea)
from PySide6.QtCore import Qt, QPoint, QSize, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QColor, QIcon, QFont, QCursor

class NoteItemWidget(QFrame):
    """A single row in the side menu representing a note."""
    clicked = Signal(str) # note_id
    delete_clicked = Signal(str) # note_id

    def __init__(self, note_id, content):
        super().__init__()
        self.note_id = note_id
        self.setFixedHeight(50)
        self.setCursor(Qt.PointingHandCursor)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        # Preview Text
        preview = content.strip().split('\n')[0][:20]
        if not preview: preview = "New Note"
        
        self.lbl = QLabel(preview)
        self.lbl.setStyleSheet("color: white; border: none; background: transparent;")
        
        # Delete Button
        self.del_btn = QPushButton("🗑") # Trash icon
        self.del_btn.setFixedSize(20, 20)
        self.del_btn.setStyleSheet("""
            QPushButton { 
                background: transparent; color: #aaa; border: none; 
            }
            QPushButton:hover { 
                color: #ff5f57; 
            }
        """)
        self.del_btn.clicked.connect(self.on_delete)
        
        self.layout.addWidget(self.lbl)
        self.layout.addStretch()
        self.layout.addWidget(self.del_btn)
        
        self.setObjectName("NoteItem")

    def mousePressEvent(self, event):
        self.clicked.emit(self.note_id)
        super().mousePressEvent(event)

    def on_delete(self):
        self.delete_clicked.emit(self.note_id)

class SideMenu(QWidget):
    """Sliding side menu."""
    def __init__(self, parent=None):
        super().__init__(parent)
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

import shutil

class StickyNote(QMainWindow):
    THEMES = [
        {"name": "Dark", "bg": (30, 30, 30), "text": "#ffffff", "border": "rgba(255, 255, 255, 30)"},
        {"name": "Classic", "bg": (255, 247, 128), "text": "#000000", "border": "rgba(0, 0, 0, 30)"},
        {"name": "Ocean", "bg": (30, 60, 90), "text": "#ffffff", "border": "rgba(255, 255, 255, 30)"},
        {"name": "Rose", "bg": (255, 200, 200), "text": "#000000", "border": "rgba(0, 0, 0, 30)"},
        {"name": "Mint", "bg": (200, 255, 200), "text": "#000000", "border": "rgba(0, 0, 0, 30)"},
    ]

    def __init__(self):
        super().__init__()
        
        # Determine AppData path
        app_data_dir = os.path.join(os.getenv('LOCALAPPDATA'), 'Klarion')
        os.makedirs(app_data_dir, exist_ok=True)
        self.notes_file = os.path.join(app_data_dir, "notes_data.json")
        
        # Migration: Check for local file
        local_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes_data.json")
        # Also check cwd just in case
        cwd_file = "notes_data.json"
        
        if not os.path.exists(self.notes_file):
            if os.path.exists(local_file):
                try:
                    shutil.move(local_file, self.notes_file)
                    print(f"Migrated data from {local_file} to {self.notes_file}")
                except Exception as e:
                    print(f"Migration failed: {e}")
            elif os.path.exists(cwd_file):
                 try:
                    shutil.move(cwd_file, self.notes_file)
                    print(f"Migrated data from {cwd_file} to {self.notes_file}")
                 except Exception as e:
                    print(f"Migration failed: {e}")

        self.is_pinned = False
        self.current_opacity = 240
        self.theme_index = 0
        
        self.notes_data = [] # List of dicts {id, content, timestamp}
        self.active_note_id = None

        # Window Setup
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(350, 400)
        
        # --- Main UI Construction ---
        self.central_widget = QWidget()
        self.central_widget.setObjectName("Container")
        self.setCentralWidget(self.central_widget)
        
        self.root_layout = QHBoxLayout(self.central_widget) # Horizontal: [Menu] [Content]
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # Side Menu (Added to layout typically, but for sliding OVERLAY effect, 
        # it's often better to NOT be in the layout or animate layout stretch.
        # Here we will put it in the layout but animate its width.)
        self.side_menu = SideMenu()
        self.side_menu.add_btn.clicked.connect(self.create_new_note)
        self.root_layout.addWidget(self.side_menu)

        # Main Content Wrapper
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

        # Burger Button
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

        self.slider_label = QLabel("👁")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(50, 255)
        self.slider.setValue(240)
        self.slider.setFixedWidth(60)
        self.slider.valueChanged.connect(self.update_opacity)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self.close_app)
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        
        self.header_layout.addWidget(self.menu_btn) # Burger first!
        self.header_layout.addWidget(self.pin_btn)
        self.header_layout.addWidget(self.theme_btn)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.slider_label)
        self.header_layout.addWidget(self.slider)
        self.header_layout.addStretch()

        # Minimize Button
        self.min_btn = QPushButton("─")
        self.min_btn.setFixedSize(30, 30)
        self.min_btn.clicked.connect(self.showMinimized)
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.header_layout.addWidget(self.min_btn)

        self.header_layout.addWidget(self.close_btn)

        self.content_layout.addWidget(self.title_bar)

        # Text Edit
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
        self.grip = QSizeGrip(self.content_area) # Parented to content!
        self.grip.setFixedSize(20, 20)
        self.bottom_layout.addWidget(self.grip)
        
        self.content_layout.addWidget(self.bottom_bar)

        # Animation
        self.menu_animation = QPropertyAnimation(self.side_menu, b"maximumWidth")
        self.menu_animation.setDuration(300)
        self.menu_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.menu_open = False

        # Dragging logic
        self.old_pos = None

        # Init
        self.load_data()
        self.update_style()

    def load_data(self):
        if os.path.exists(self.notes_file):
            try:
                with open(self.notes_file, "r") as f:
                    data = json.load(f)
                    
                    # Check if migration needed (old format vs new)
                    # Old format: direct keys "content", "pinned", etc.
                    # New format: "notes": [], "settings": {}
                    
                    if "notes" in data:
                        # New format
                        self.notes_data = data.get("notes", [])
                        settings = data.get("settings", {})
                        self.is_pinned = settings.get("pinned", False)
                        self.current_opacity = settings.get("opacity", 240)
                        self.theme_index = settings.get("theme_index", 0)
                        self.active_note_id = data.get("active_note_id")
                    else:
                        # Legacy format migration
                        content = data.get("content", "")
                        note_id = str(uuid.uuid4())
                        self.notes_data = [{"id": note_id, "content": content, "timestamp": time.time()}]
                        self.active_note_id = note_id
                        
                        self.is_pinned = data.get("pinned", False)
                        self.current_opacity = data.get("opacity", 240)
                        self.theme_index = data.get("theme_index", 0)

            except Exception as e:
                print(f"Error loading: {e}")
        
        # Ensure at least one note
        if not self.notes_data:
            self.create_new_note(save=False) # Don't save empty immediately
        
        # Apply settings
        self.slider.setValue(self.current_opacity)
        if self.is_pinned:
            self.pin_btn.setChecked(True)
            self.toggle_pin()
        
        # Load active note
        self.load_active_note_content()
        self.refresh_menu_list()

    def load_active_note_content(self):
        # Find note object
        note = next((n for n in self.notes_data if n["id"] == self.active_note_id), None)
        if note:
            self.text_edit.blockSignals(True) # Prevent save loop
            self.text_edit.setPlainText(note["content"])
            self.text_edit.blockSignals(False)
        elif self.notes_data:
            # Fallback if id not found
            self.active_note_id = self.notes_data[0]["id"]
            self.load_active_note_content()

    def create_new_note(self, save=True):
        new_id = str(uuid.uuid4())
        new_note = {"id": new_id, "content": "", "timestamp": time.time()}
        self.notes_data.insert(0, new_note) # Add to top
        self.active_note_id = new_id
        
        # UI Update
        self.text_edit.blockSignals(True)
        self.text_edit.clear()
        self.text_edit.blockSignals(False)
        
        self.refresh_menu_list()
        if save:
            self.save_data()
            
        # If menu open, auto-close? No, user might want to see it added.
        # But we should focus text edit
        self.text_edit.setFocus()

    def refresh_menu_list(self):
        # Clear existing items
        layout = self.side_menu.scroll_layout
        while layout.count() > 1: # Keep the stretch item at end
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add items
        for note in self.notes_data:
            item = NoteItemWidget(note["id"], note["content"])
            item.clicked.connect(self.switch_note)
            item.delete_clicked.connect(self.delete_note)
            
            # Highlight active
            if note["id"] == self.active_note_id:
               item.setStyleSheet("NoteItemWidget { background-color: rgba(255, 255, 255, 0.1); border-radius: 5px; }")
               
            layout.insertWidget(layout.count()-1, item)

    def switch_note(self, note_id):
        if note_id == self.active_note_id: return
        
        # Current one is already saved via textChange
        self.active_note_id = note_id
        self.load_active_note_content()
        self.refresh_menu_list()
        self.save_data() # Update active ID in persistence

    def delete_note(self, note_id):
        # Remove from list
        self.notes_data = [n for n in self.notes_data if n["id"] != note_id]
        
        if not self.notes_data:
            # Create new one if empty
            self.create_new_note(save=False)
        elif note_id == self.active_note_id:
            # Switch to first
            self.active_note_id = self.notes_data[0]["id"]
            self.load_active_note_content()
            
        self.refresh_menu_list()
        self.save_data()

    def on_text_changed(self):
        content = self.text_edit.toPlainText()
        # Update memory
        for note in self.notes_data:
            if note["id"] == self.active_note_id:
                note["content"] = content
                note["timestamp"] = time.time()
                break
        
        # Debounce logic could go here, but doing direct save is safer for "seamless" feel if small file
        self.save_data()
        
        # Also need to update menu preview if user types first line!
        # This might be expensive on formatted text, but for plain text it's fast.
        # We'll just trigger it occasionally or accept it updates on restart/switch?
        # Let's try to update the specific widget? Too complex.
        # Just assume menu preview updates on next refresh.

    def save_data(self):
        data = {
            "active_note_id": self.active_note_id,
            "notes": self.notes_data,
            "settings": {
                "pinned": self.is_pinned,
                "opacity": self.current_opacity,
                "theme_index": self.theme_index
            }
        }
        try:
            with open(self.notes_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving: {e}")

    def toggle_menu(self):
        start_w = self.side_menu.width()
        end_w = 150 if start_w == 0 else 0
        
        self.menu_animation.setStartValue(start_w)
        self.menu_animation.setEndValue(end_w)
        self.menu_animation.start()
        
        self.menu_open = (end_w != 0)
        self.refresh_menu_list() # Ensure fresh previews on open

    # --- Style & Boilerplate (Same as before but updated selectors) ---
    def update_style(self):
        bg_alpha = self.current_opacity
        theme = self.THEMES[self.theme_index]
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

    def update_opacity(self, value):
        # User wants a curve so it doesn't become translucent too quickly.
        # We map the linear slider value to a non-linear alpha.
        # Normalize slider (50-255) to 0.0-1.0
        t = (value - 50) / 205.0
        if t < 0: t = 0
        
        # Apply curve: Power < 1 makes the curve bulge upwards (staying higher for longer)
        # alpha_factor = t^0.3 (roughly cube root)
        curve_t = t ** 0.4 
        
        # Map back to 50-255
        new_alpha = 50 + (205 * curve_t)
        
        self.current_opacity = int(new_alpha)
        self.update_style()
    
    def cycle_theme(self):
        self.theme_index = (self.theme_index + 1) % len(self.THEMES)
        self.update_style()
        self.save_data() # Save theme immediately

    def toggle_pin(self):
        self.is_pinned = self.pin_btn.isChecked()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.is_pinned)
        self.show()

    def close_app(self):
        self.save_data()
        self.close()

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
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    # Fix Taskbar Icon/Name grouping (Windows specific)
    import ctypes
    myappid = 'chudasmat.klarion.sticky.v1' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    app.setApplicationName("klarion")
    
    icon_path = resource_path("klarion.ico")
    app.setWindowIcon(QIcon(icon_path))
    
    window = StickyNote()
    window.setWindowIcon(QIcon(icon_path))
    window.setWindowTitle("klarion") # Update title for taskbar text
    window.show()
    sys.exit(app.exec())
