from flask import Blueprint, request, jsonify, send_file, render_template
from .database import get_db_connection
import sqlite3
import os
import json
from werkzeug.utils import secure_filename
import pandas as pd
from datetime import datetime

products_bp = Blueprint('products', __name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_products_table():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
    if not c.fetchone():
        c.execute('''CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            unit TEXT NOT NULL,
            purchase_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            image TEXT,
            note TEXT
        )''')
        initial_data = [
            ('sp01', 'Sản phẩm 1', 'Cái', 10000, 15000, 10, '', ''),
            ('sp02', 'Sản phẩm 2', 'Cái', 20000, 30000, 20, '', ''),
            ('sp03', 'Sản phẩm 3', 'Cái', 30000, 45000, 33, '', ''),
            ('sp04', 'Sản phẩm 4', 'Cái', 40000, 60000, 40, '', ''),
            ('sp05', 'Sản phẩm 5', 'Cái', 50000, 75000, 50, '', '')
        ]
        c.executemany('INSERT INTO products (code, name, unit, purchase_price, selling_price, quantity, image, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', initial_data)
        conn.commit()
    conn.close()

@products_bp.route('/products', methods=['GET'])
def products_page():
    ensure_products_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    products = c.fetchall()
    conn.close()
    return render_template('products.html', products=products)

@products_bp.route('/api/products', methods=['GET'])
def get_products():
    ensure_products_table()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    search = request.args.get('search', '')
    offset = (page - 1) * per_page

    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT * FROM products WHERE code LIKE ? OR name LIKE ? LIMIT ? OFFSET ?"
    c.execute(query, (f'%{search}%', f'%{search}%', per_page, offset))
    products = c.fetchall()
    c.execute("SELECT COUNT(*) FROM products WHERE code LIKE ? OR name LIKE ?", (f'%{search}%', f'%{search}%'))
    total = c.fetchone()[0]
    conn.close()

    products_list = []
    for product in products:
        products_list.append({
            'id': product['id'],
            'code': product['code'],
            'name': product['name'],
            'unit': product['unit'],
            'purchase_price': float(product['purchase_price']),
            'selling_price': float(product['selling_price']),
            'quantity': int(product['quantity']),
            'image': product['image'],
            'note': product['note']
        })

    return jsonify({
        'products': products_list,
        'page': page,
        'per_page': per_page,
        'total': total
    })

@products_bp.route('/api/products/search', methods=['GET'])
def search_products_suggestions():
    ensure_products_table()
    search = request.args.get('q', '')
    conn = get_db_connection()
    c = conn.cursor()
    if search:
        # Sắp xếp theo mức độ khớp: sản phẩm bắt đầu bằng từ khóa lên đầu
        query = """
        SELECT id, name, purchase_price, selling_price 
        FROM products 
        WHERE name LIKE ? 
        ORDER BY 
            CASE 
                WHEN name LIKE ? THEN 0 
                WHEN name LIKE ? THEN 1 
                ELSE 2 
            END, name ASC
        """
        c.execute(query, (f'%{search}%', f'{search}%', f'%{search}%'))
    else:
        query = "SELECT id, name, purchase_price, selling_price FROM products ORDER BY name ASC"
        c.execute(query)
    products = c.fetchall()
    conn.close()

    suggestions = []
    for product in products:
        suggestions.append({
            'id': product['id'],
            'name': product['name'],
            'purchase_price': float(product['purchase_price']),
            'selling_price': float(product['selling_price'])
        })

    return jsonify(suggestions)

@products_bp.route('/api/products', methods=['POST'])
def create_product():
    ensure_products_table()
    data = request.form
    code = data.get('code')
    name = data.get('name')
    unit = data.get('unit')
    purchase_price = float(data.get('purchase_price', 0))
    selling_price = float(data.get('selling_price', 0))
    note = data.get('note')

    if not all([code, name, unit, purchase_price, selling_price]):
        return jsonify({'message': 'Thiếu thông tin bắt buộc'}), 400

    image_path = ''
    if 'image' in request.files:
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            image_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(image_path)

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO products (code, name, unit, purchase_price, selling_price, quantity, image, note)
                     VALUES (?, ?, ?, ?, ?, 0, ?, ?)''',
                  (code, name, unit, purchase_price, selling_price, image_path, note))
        conn.commit()
        return jsonify({'message': 'Sản phẩm đã được tạo'}), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()

@products_bp.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    ensure_products_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT image FROM products WHERE id = ?", (id,))
    product = c.fetchone()
    if not product:
        conn.close()
        return jsonify({'message': 'Sản phẩm không tồn tại'}), 404

    if product['image']:
        try:
            os.remove(product['image'])
        except:
            pass

    c.execute("DELETE FROM products WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Sản phẩm đã được xóa'})

@products_bp.route('/api/products/export/excel', methods=['GET'])
def export_excel():
    ensure_products_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT code, name, unit, purchase_price, selling_price, quantity, note FROM products")
    products = c.fetchall()
    conn.close()

    data = []
    for product in products:
        data.append({
            'Mã': product['code'],
            'Tên': product['name'],
            'Đơn vị': product['unit'],
            'Giá nhập': product['purchase_price'],
            'Giá bán': product['selling_price'],
            'Số lượng': product['quantity'],
            'Ghi chú': product['note']
        })

    df = pd.DataFrame(data)
    excel_file = 'san_pham.xlsx'
    df.to_excel(excel_file, index=False)

    return send_file(excel_file, as_attachment=True, download_name='san_pham.xlsx')