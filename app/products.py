from flask import Blueprint, request, jsonify, send_file, render_template
from .database import get_db_connection
from werkzeug.utils import secure_filename
import os
import pandas as pd
from config import Config
import sqlite3
import tempfile

products_bp = Blueprint('products', __name__)

def ensure_products_table():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
    if not c.fetchone():
        c.execute('''CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            unit TEXT NOT NULL,
            purchase_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            image TEXT,
            note TEXT
        )''')
        c.execute("INSERT INTO products (code, name, unit, purchase_price, selling_price, quantity, image, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  ('sp03', 'Cà phê gói', 'gói', 100000, 200000, 33, '', ''))
        conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

@products_bp.route('/products', methods=['GET'])
def products_page():
    return render_template('products.html')

@products_bp.route('/api/products', methods=['GET'])
def get_products():
    ensure_products_table()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    search = request.args.get('search', '')
    offset = (page - 1) * per_page

    conn = get_db_connection()
    c = conn.cursor()
    try:
        query = "SELECT id, code, name, unit, purchase_price, selling_price, quantity, image, note FROM products WHERE code LIKE ? OR name LIKE ?"
        c.execute(query, (f'%{search}%', f'%{search}%'))
        products = c.fetchall()
        total = len(products)
        c.execute(query + " LIMIT ? OFFSET ?", (f'%{search}%', f'%{search}%', per_page, offset))
        products = c.fetchall()
        print(f"Products fetched: {len(products)}")
        return jsonify({
            'products': [{'id': p['id'], 'code': p['code'], 'name': p['name'], 'unit': p['unit'],
                          'purchase_price': p['purchase_price'], 'selling_price': p['selling_price'],
                          'quantity': p['quantity'], 'image': p['image'], 'note': p['note']} for p in products],
            'total': total,
            'page': page,
            'per_page': per_page
        }), 200
    except sqlite3.OperationalError as e:
        print(f"Database error: {str(e)}")
        return jsonify({'message': f'Lỗi cơ sở dữ liệu: {str(e)}'}), 500
    finally:
        conn.close()

@products_bp.route('/api/products', methods=['POST'])
def add_product():
    ensure_products_table()
    code = request.form.get('code')
    name = request.form.get('name')
    unit = request.form.get('unit')
    purchase_price = request.form.get('purchase_price')
    selling_price = request.form.get('selling_price')
    note = request.form.get('note', '')
    image = request.files.get('image')
    image_path = ''
    quantity = 0  # Mặc định số lượng là 0 khi tạo sản phẩm mới

    if not all([code, name, unit, purchase_price, selling_price]):
        missing = [k for k, v in {"code": code, "name": name, "unit": unit, "purchase_price": purchase_price, "selling_price": selling_price}.items() if not v]
        return jsonify({'message': f'Thiếu các trường bắt buộc: {", ".join(missing)}'}), 400

    try:
        purchase_price = float(purchase_price)
        selling_price = float(selling_price)
    except ValueError:
        return jsonify({'message': 'Định dạng giá không hợp lệ'}), 400

    if image and allowed_file(image.filename):
        filename = secure_filename(image.filename)
        image_path = os.path.join(Config.UPLOAD_FOLDER, filename)
        try:
            image.save(image_path)
        except Exception as e:
            return jsonify({'message': f'Lỗi khi lưu hình ảnh: {str(e)}'}), 500

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO products (code, name, unit, purchase_price, selling_price, quantity, image, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (code, name, unit, purchase_price, selling_price, quantity, image_path, note))
        conn.commit()
        return jsonify({'message': 'Thêm sản phẩm thành công'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'message': 'Mã sản phẩm đã tồn tại'}), 400
    except sqlite3.OperationalError as e:
        return jsonify({'message': f'Lỗi cơ sở dữ liệu: {str(e)}'}), 500
    finally:
        conn.close()

@products_bp.route('/api/products/<int:id>', methods=['PUT'])
def update_product(id):
    ensure_products_table()
    data = request.form
    image = request.files.get('image')
    image_path = data.get('image', '')

    if image and allowed_file(image.filename):
        filename = secure_filename(image.filename)
        image_path = os.path.join(Config.UPLOAD_FOLDER, filename)
        image.save(image_path)

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""UPDATE products SET code = ?, name = ?, unit = ?, purchase_price = ?, selling_price = ?, quantity = ?, image = ?, note = ?
                     WHERE id = ?""",
                  (data.get('code'), data.get('name'), data.get('unit'), float(data.get('purchase_price', 0)),
                   float(data.get('selling_price', 0)), int(data.get('quantity', 0)), image_path, data.get('note', ''), id))
        conn.commit()
        return jsonify({'message': 'Cập nhật sản phẩm thành công'}), 200
    except sqlite3.IntegrityError:
        return jsonify({'message': 'Mã sản phẩm đã tồn tại'}), 400
    finally:
        conn.close()

@products_bp.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    ensure_products_table()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Xóa sản phẩm thành công'}), 200

@products_bp.route('/api/products/export/excel', methods=['GET'])
def export_excel():
    ensure_products_table()
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM products")
        products = c.fetchall()
        conn.close()

        df = pd.DataFrame(products, columns=['ID', 'Mã', 'Tên', 'Đơn vị', 'Giá nhập', 'Giá bán', 'Số lượng', 'Hình ảnh', 'Ghi chú']) if products else pd.DataFrame(columns=['ID', 'Mã', 'Tên', 'Đơn vị', 'Giá nhập', 'Giá bán', 'Số lượng', 'Hình ảnh', 'Ghi chú'])
        
        # Sử dụng thư mục tạm để tránh lỗi quyền ghi
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            excel_file = tmp.name
            df.to_excel(excel_file, index=False, engine='openpyxl')
        
        return send_file(excel_file, as_attachment=True, download_name='san_pham.xlsx')
    except Exception as e:
        return jsonify({'message': 'Lỗi khi xuất Excel: ' + str(e)}), 500

@products_bp.route('/api/products/suggest', methods=['GET'])
def suggest_products():
    ensure_products_table()
    query = request.args.get('query', '')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, code, name, unit, purchase_price, selling_price, quantity FROM products WHERE code LIKE ? OR name LIKE ? LIMIT 5",
              (f'%{query}%', f'%{query}%'))
    products = c.fetchall()
    conn.close()

    return jsonify({
        'suggestions': [{'id': p['id'], 'code': p['code'], 'name': p['name'], 'unit': p['unit'],
                         'purchase_price': p['purchase_price'], 'selling_price': p['selling_price'],
                         'quantity': p['quantity']} for p in products]
    }), 200