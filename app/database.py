import sqlite3
import os

DATABASE = 'inventory.db'

def get_db_connection():
    conn = sqlite3.connect('database.db', timeout=30)  # Thêm timeout=10 giây
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
    conn = get_db_connection()
    conn.close()
    # Các bảng sẽ được tạo trong ensure_products_table() và ensure_invoices_table()