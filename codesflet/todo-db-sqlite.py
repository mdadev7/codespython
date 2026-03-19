import sqlite3
import math
from dataclasses import field
from typing import Callable, Optional
import flet as ft

# --- Database Layer (SQLite) ---
DB_NAME = "todo_app.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            completed BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def db_add_task(name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (task_name, completed) VALUES (?, ?)", (name, False))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def db_get_tasks(search_query: str = "", page: int = 1, per_page: int = 5, status_filter: str = "all"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []

    if search_query:
        query += " AND task_name LIKE ?"
        params.append(f"%{search_query}%")

    if status_filter == "active":
        query += " AND completed = 0"
    elif status_filter == "completed":
        query += " AND completed = 1"

    offset = (page - 1) * per_page
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Count total for pagination
    count_query = "SELECT COUNT(*) FROM tasks WHERE 1=1"
    count_params = []
    if search_query:
        count_query += " AND task_name LIKE ?"
        count_params.append(f"%{search_query}%")
    if status_filter == "active":
        count_query += " AND completed = 0"
    elif status_filter == "completed":
        count_query += " AND completed = 1"
        
    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()[0]
    
    conn.close()
    
    return [{"id": row["id"], "task_name": row["task_name"], "completed": bool(row["completed"])} for row in rows], total_count

def db_update_task(task_id: int, completed: bool, new_name: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if new_name is not None:
        cursor.execute("UPDATE tasks SET task_name = ?, completed = ? WHERE id = ?", (new_name, completed, task_id))
    else:
        cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?", (completed, task_id))
    conn.commit()
    conn.close()

def db_delete_task(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

# Initialize DB
init_db()

# --- Flet Components ---

@ft.control
class Task(ft.Column):
    task_id: int = 0
    task_name: str = ""
    completed: bool = False
    on_status_change: Callable[[], None] = field(default=lambda: None)
    on_delete: Callable[["Task"], None] = field(default=lambda task: None)
    on_save: Callable[["Task", str], None] = field(default=lambda task, name: None)

    def init(self):
        self.display_task = ft.Checkbox(
            value=self.completed, label=self.task_name, on_change=self.status_changed
        )
        self.edit_name = ft.TextField(value=self.task_name, expand=1)

        self.display_view = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self.display_task,
                ft.Row(
                    spacing=0,
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.CREATE_OUTLINED,
                            tooltip="Edit To-Do",
                            on_click=self.edit_clicked,
                        ),
                        ft.IconButton(
                            ft.Icons.DELETE_OUTLINE,
                            tooltip="Delete To-Do",
                            on_click=self.delete_clicked,
                        ),
                    ],
                ),
            ],
        )

        self.edit_view = ft.Row(
            visible=False,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self.edit_name,
                ft.IconButton(
                    icon=ft.Icons.DONE_OUTLINE_OUTLINED,
                    icon_color=ft.Colors.GREEN,
                    tooltip="Update To-Do",
                    on_click=self.save_clicked,
                ),
            ],
        )
        self.controls = [self.display_view, self.edit_view]

    def edit_clicked(self, e):
        self.edit_name.value = self.display_task.label
        self.display_view.visible = False
        self.edit_view.visible = True
        self.update()

    def save_clicked(self, e):
        new_name = self.edit_name.value.strip()
        if new_name:
            self.on_save(self, new_name)
            self.display_task.label = new_name
            self.display_view.visible = True
            self.edit_view.visible = False
            self.update()

    def status_changed(self, e):
        self.completed = self.display_task.value
        self.on_status_change()

    def delete_clicked(self, e):
        self.on_delete(self)

@ft.control
class TodoApp(ft.Column):
    def init(self):
        self.page_size = 5
        self.current_page = 1
        self.total_items = 0
        self.search_query = ""
        self.current_filter = "all"
        
        self.new_task = ft.TextField(hint_text="What needs to be done?", expand=True)
        
        self.search_field = ft.TextField(
            hint_text="Search tasks...", 
            expand=True, 
            on_change=self.on_search_change
            # Removed prefix_icon to ensure compatibility with 0.81.0 if strict
        )

        # FIX: Use a Column with scroll=True instead of Container with scroll
        self.tasks_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, height=400)

        # Filter Buttons
        self.btn_all = ft.ElevatedButton("All", on_click=lambda e: self.set_filter("all"))
        self.btn_active = ft.ElevatedButton("Active", on_click=lambda e: self.set_filter("active"))
        self.btn_completed = ft.ElevatedButton("Completed", on_click=lambda e: self.set_filter("completed"))
        
        self.filter_row = ft.Row(
            controls=[self.btn_all, self.btn_active, self.btn_completed],
            alignment=ft.MainAxisAlignment.START
        )
        
        # Set initial active state visually without calling update()
        self.btn_all.bgcolor = ft.Colors.BLUE_100

        self.prev_btn = ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=self.prev_page, disabled=True)
        self.next_btn = ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=self.next_page, disabled=True)
        self.page_info = ft.Text("Page 1 of 1")

        self.width = 600
        self.controls = [
            ft.Row(controls=[self.new_task, ft.FloatingActionButton(icon=ft.Icons.ADD, on_click=self.add_clicked)]),
            ft.Divider(),
            ft.Row(controls=[self.search_field]),
            self.filter_row,
            # Removed Container wrapper, added Column directly
            self.tasks_column, 
            ft.Divider(),
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    self.prev_btn,
                    self.page_info,
                    self.next_btn
                ]
            )
        ]

    def update_filter_buttons(self):
        """Highlights the active filter button."""
        # Reset colors
        self.btn_all.bgcolor = None
        self.btn_active.bgcolor = None
        self.btn_completed.bgcolor = None
        
        # Highlight selected
        active_color = ft.Colors.BLUE_100
        if self.current_filter == "all":
            self.btn_all.bgcolor = active_color
        elif self.current_filter == "active":
            self.btn_active.bgcolor = active_color
        elif self.current_filter == "completed":
            self.btn_completed.bgcolor = active_color
        
        if self.page:
            self.update()

    def set_filter(self, filter_name: str):
        self.current_filter = filter_name
        self.current_page = 1
        self.update_filter_buttons()
        self.load_data()

    def load_data(self):
        if not self.page:
            return

        tasks_data, total_count = db_get_tasks(
            search_query=self.search_query,
            page=self.current_page,
            per_page=self.page_size,
            status_filter=self.current_filter
        )
        
        self.total_items = total_count
        
        # Clear controls safely
        self.tasks_column.controls.clear()

        for item in tasks_data:
            # 1. Create the Task control instance first
            task_control = Task(
                task_id=item["id"],
                task_name=item["task_name"],
                completed=item["completed"]
                # Leave callbacks empty for now
            )
            
            # 2. Now assign the callbacks using the fully created task_control
            # We define small helper functions or assign directly to properties
            task_control.on_status_change = lambda tc=task_control: self.task_status_change(tc)
            task_control.on_delete = lambda tc=task_control: self.task_delete(tc)
            task_control.on_save = lambda tc, name: self.task_save(tc, name)
            
            self.tasks_column.controls.append(task_control)

        self.update_pagination_controls()
        self.update()

    def update_pagination_controls(self):
        total_pages = max(1, math.ceil(self.total_items / self.page_size))
        self.page_info.value = f"Page {self.current_page} of {total_pages}"
        
        self.prev_btn.disabled = (self.current_page <= 1)
        self.next_btn.disabled = (self.current_page >= total_pages)

    def add_clicked(self, e):
        name = self.new_task.value.strip()
        if not name:
            return
        
        db_add_task(name)
        self.new_task.value = ""
        self.current_page = 1 
        self.load_data()

    def task_status_change(self, task_obj: Task):
        db_update_task(task_obj.task_id, task_obj.completed)
        if self.current_filter != "all":
            self.load_data()
        else:
            self.update()

    def task_delete(self, task_obj: Task):
        db_delete_task(task_obj.task_id)
        self.load_data()

    def task_save(self, task_obj: Task, new_name: str):
        db_update_task(task_obj.task_id, task_obj.completed, new_name=new_name)
        self.load_data()

    def on_search_change(self, e):
        self.search_query = self.search_field.value.strip()
        self.current_page = 1
        self.load_data()

    def prev_page(self, e):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def next_page(self, e):
        total_pages = math.ceil(self.total_items / self.page_size)
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_data()

def main(page: ft.Page):
    page.title = "Persistent To-Do App"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE
    
    app = TodoApp()
    page.add(app)
    
    # Load data after adding to page
    app.load_data()

if __name__ == "__main__":
    ft.run(main)