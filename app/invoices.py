from flask import Blueprint, request, jsonify, render_template
from .database import get_db_connection
import sqlite3
import json

invoices_bp = Blueprint('invoices', __name__)

def ensure_invoices_table():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invoices'")
    if not c.fetchone():
        c.execute('''CREATE TABLE invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            purpose TEXT NOT NULL,
            total REAL NOT NULL,
            discount REAL NOT NULL,
            items TEXT NOT NULL,
            note TEXT
        )''')
        conn.commit()
    conn.close()

@invoices_bp.route('/invoices', methods=['GET'])
def invoices_page():
    return render_template('invoices.html')

@invoices_bp.route('/api/invoices', methods=['GET'])
def get_invoices():
    ensure_invoices_table()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    search = request.args.get('search', '')
    offset = (page - 1) * per_page

    conn = get_db_connection()
    c = conn.cursor()
    try:
        query = "SELECT id, date, type, purpose, total, discount, items, note FROM invoices WHERE purpose LIKE ?"
        c.execute(query, (f'%{search}%',))
        invoices = c.fetchall()
        total = len(invoices)
        c.execute(query + " LIMIT ? OFFSET ?", (f'%{search}%', per_page, offset))
        invoices = c.fetchall()
        print(f"Invoices fetched: {len(invoices)}") # Debug server
        return jsonify({
            'invoices': [{'id': i['id'], 'date': i['date'], 'type': i['type'], 'purpose': i['purpose'],
                          'total': i['total'], 'discount': i['discount'], 'items': i['items'], 'note': i['note']} for i in invoices],
            'total': total,
            'page': page,
            'per_page': per_page
        }), 200
    except sqlite3.OperationalError as e:
        print(f"Database error: {str(e)}")
        return jsonify({'message': f'Lỗi cơ sở dữ liệu: {str(e)}'}), 500
    finally:
        conn.close()

@invoices_bp.route('/api/invoices', methods=['POST'])
def add_invoice():
    ensure_invoices_table()
    date = request.form.get('date')
    type_ = request.form.get('type')
    purpose = request.form.get('purpose')
    total = request.form.get('total')
    discount = request.form.get('discount', 0)
    items = request.form.get('items')
    note = request.form.get('note', '')

    if not all([date, type_, purpose, total, items]):
        missing = [k for k, v in {"date": date, "type": type_, "purpose": purpose, "total": total, "items": items}.items() if not v]
        return jsonify({'message': f'Thiếu các trường bắt buộc: {", ".join(missing)}'}), 400

    try:
        total = float(total)
        discount = float(discount)
    except ValueError:
        return jsonify({'message': 'Định dạng tổng tiền hoặc giảm giá không hợp lệ'}), 400

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO invoices (date, type, purpose, total, discount, items, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (date, type_, purpose, total, discount, items, note))
        
        # Cập nhật số lượng sản phẩm
        items_list = json.loads(items)
        for item in items_list:
            product_id = item.get('id')
            quantity = item.get('quantity')
            if type_ == 'Nhập':
                c.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (quantity, product_id))
            elif type_ == 'Xuất':
                # Kiểm tra số lượng tồn kho trước khi xuất
                c.execute("SELECT quantity FROM products WHERE id = ?", (product_id,))
                current_quantity = c.fetchone()['quantity']
                if current_quantity < quantity:
                    conn.close()
                    return jsonify({'message': f'Số lượng xuất vượt quá tồn kho cho sản phẩm ID {product_id}'}), 400
                c.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (quantity, product_id))
        
        conn.commit()
        return jsonify({'message': 'Thêm hóa đơn thành công'}), 201
    except sqlite3.OperationalError as e:
        return jsonify({'message': f'Lỗi cơ sở dữ liệu: {str(e)}'}), 500
    except ValueError as e:
        return jsonify({'message': f'Lỗi dữ liệu: {str(e)}'}), 400
    finally:
        conn.close()