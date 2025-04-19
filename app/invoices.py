from flask import Blueprint, request, jsonify, render_template, send_file
from .database import get_db_connection
import sqlite3
import json
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from io import BytesIO

invoices_bp = Blueprint('invoices', __name__)

def ensure_invoices_table():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Kiểm tra và tạo bảng invoices nếu chưa tồn tại
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invoices'")
    if not c.fetchone():
        c.execute('''CREATE TABLE invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            purpose TEXT,
            total REAL NOT NULL,
            discount REAL NOT NULL,
            discount_type TEXT NOT NULL DEFAULT 'fixed',
            items TEXT NOT NULL,
            note TEXT
        )''')
    else:
        # Kiểm tra và thêm cột discount_type nếu chưa có
        c.execute("PRAGMA table_info(invoices)")
        columns = [col[1] for col in c.fetchall()]
        if 'discount_type' not in columns:
            c.execute("ALTER TABLE invoices ADD COLUMN discount_type TEXT DEFAULT 'fixed'")
    
    # Kiểm tra và tạo bảng invoice_items nếu chưa tồn tại
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invoice_items'")
    if not c.fetchone():
        c.execute('''CREATE TABLE invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            custom_selling_price REAL,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )''')
    else:
        # Kiểm tra và thêm cột custom_selling_price nếu chưa có
        c.execute("PRAGMA table_info(invoice_items)")
        columns = [col[1] for col in c.fetchall()]
        if 'custom_selling_price' not in columns:
            c.execute("ALTER TABLE invoice_items ADD COLUMN custom_selling_price REAL")

    conn.commit()
    conn.close()

@invoices_bp.route('/invoices', methods=['GET'])
def invoices_page():
    ensure_invoices_table()
    return render_template('invoices.html')

@invoices_bp.route('/api/invoices', methods=['GET'])
def get_invoices():
    ensure_invoices_table()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    search = request.args.get('search', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    offset = (page - 1) * per_page

    conn = get_db_connection()
    c = conn.cursor()
    try:
        query = "SELECT id, date, type, purpose, total, discount, discount_type, items, note FROM invoices WHERE 1=1"
        params = []

        if search:
            query += " AND (purpose LIKE ? OR items LIKE ?)"
            params.extend([f'%{search}%', f'%{search}%'])

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        c.execute(query, params)
        invoices = c.fetchall()

        filtered_invoices = []
        total_import = 0
        total_export = 0
        for invoice in invoices:
            items = json.loads(invoice['items'] or '[]')
            if search:
                match = False
                for item in items:
                    if search.lower() in item.get('name', '').lower():
                        match = True
                        break
                if not match and (invoice['purpose'] is None or search.lower() not in invoice['purpose'].lower()):
                    continue
            filtered_invoices.append(invoice)
            
            # Tính tổng tiền nhập và xuất
            if invoice['type'] == 'Nhập':
                total_import += float(invoice['total'])
            elif invoice['type'] == 'Xuất':
                total_export += float(invoice['total'])

        total = len(filtered_invoices)
        filtered_invoices = filtered_invoices[offset:offset + per_page]

        invoices_list = []
        for invoice in filtered_invoices:
            items_list = json.loads(invoice['items'])
            invoices_list.append({
                'id': invoice['id'],
                'date': invoice['date'],
                'type': invoice['type'],
                'purpose': invoice['purpose'] or '',
                'total': float(invoice['total']),
                'discount': float(invoice['discount']),
                'discount_type': invoice['discount_type'],
                'items': items_list,
                'note': invoice['note']
            })

        return jsonify({
            'invoices': invoices_list,
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_import': total_import,
            'total_export': total_export
        })
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()

@invoices_bp.route('/api/invoices/<int:id>/export/pdf', methods=['GET'])
def export_invoice_pdf(id):
    ensure_invoices_table()
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM invoices WHERE id = ?", (id,))
    invoice = c.fetchone()
    if not invoice:
        conn.close()
        return jsonify({'message': 'Hóa đơn không tồn tại'}), 404

    items = json.loads(invoice['items'])
    conn.close()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Tiêu đề hóa đơn
    p.setFont("Helvetica-Bold", 16)
    p.drawString(30 * mm, height - 30 * mm, f"HÓA ĐƠN {'NHẬP' if invoice['type'] == 'Nhập' else 'XUẤT'}")
    
    # Thông tin hóa đơn
    p.setFont("Helvetica", 12)
    y = height - 50 * mm
    p.drawString(30 * mm, y, f"ID: {invoice['id']}")
    p.drawString(30 * mm, y - 10 * mm, f"Ngày: {invoice['date']}")
    p.drawString(30 * mm, y - 20 * mm, f"Loại: {invoice['type']}")
    if invoice['purpose']:
        p.drawString(30 * mm, y - 30 * mm, f"Mục đích: {invoice['purpose']}")
    p.drawString(30 * mm, y - 40 * mm, f"Ghi chú: {invoice['note'] or ''}")

    # Tiêu đề bảng sản phẩm
    y -= 60 * mm
    p.setFont("Helvetica-Bold", 12)
    p.drawString(30 * mm, y, "Sản phẩm")
    p.drawString(80 * mm, y, "Số lượng")
    p.drawString(110 * mm, y, "Giá bán")
    p.drawString(140 * mm, y, "Thành tiền")
    p.line(30 * mm, y - 2 * mm, 180 * mm, y - 2 * mm)

    # Danh sách sản phẩm
    p.setFont("Helvetica", 12)
    y -= 10 * mm
    for item in items:
        custom_price = item.get('custom_selling_price', item.get('selling_price', 0))
        total_item = custom_price * item['quantity']
        p.drawString(30 * mm, y, item['name'])
        p.drawString(80 * mm, y, str(item['quantity']))
        p.drawString(110 * mm, y, f"{custom_price:,.0f} VNĐ")
        p.drawString(140 * mm, y, f"{total_item:,.0f} VNĐ")
        y -= 10 * mm

    # Tổng tiền và giảm giá
    y -= 10 * mm
    p.line(30 * mm, y - 2 * mm, 180 * mm, y - 2 * mm)
    p.drawString(30 * mm, y - 10 * mm, f"Giảm giá: {invoice['discount']:.0f} {'%' if invoice['discount_type'] == 'percentage' else 'VNĐ'}")
    p.drawString(30 * mm, y - 20 * mm, f"Tổng tiền: {invoice['total']:,.0f} VNĐ")

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"hoa_don_{id}.pdf", mimetype='application/pdf')

@invoices_bp.route('/api/invoices', methods=['POST'])
def create_invoice():
    ensure_invoices_table()
    data = request.form
    date = data.get('date')
    type_ = data.get('type')
    purpose = data.get('purpose') if type_ == 'Xuất' else None
    total = float(data.get('total', 0))
    discount = float(data.get('discount', 0))
    discount_type = data.get('discount_type', 'fixed')
    items = data.get('items')
    note = data.get('note')

    if not all([date, type_, items]):
        return jsonify({'message': 'Thiếu thông tin bắt buộc'}), 400

    if type_ == 'Xuất' and not purpose:
        return jsonify({'message': 'Hóa đơn xuất cần có mục đích'}), 400

    try:
        items_list = json.loads(items) if items else []
        if not items_list:
            return jsonify({'message': 'Danh sách sản phẩm không được để trống'}), 400

        conn = get_db_connection()
        c = conn.cursor()

        if type_ == 'Xuất':
            for item in items_list:
                product_id = item.get('id')
                quantity = int(item.get('quantity', 0))
                c.execute("SELECT quantity FROM products WHERE id = ?", (product_id,))
                product = c.fetchone()
                if not product:
                    conn.close()
                    return jsonify({'message': f'Sản phẩm ID {product_id} không tồn tại'}), 404
                current_quantity = product['quantity']
                if quantity > current_quantity:
                    conn.close()
                    return jsonify({'message': f'Số lượng xuất ({quantity}) của sản phẩm ID {product_id} vượt quá số lượng tồn kho ({current_quantity})'}), 400

        c.execute('''INSERT INTO invoices (date, type, purpose, total, discount, discount_type, items, note)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (date, type_, purpose, total, discount, discount_type, items, note))
        invoice_id = c.lastrowid

        for item in items_list:
            product_id = item.get('id')
            quantity = int(item.get('quantity', 0))
            if type_ == 'Nhập':
                c.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (quantity, product_id))
            elif type_ == 'Xuất':
                c.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (quantity, product_id))

        conn.commit()
        conn.close()
        return jsonify({'message': 'Hóa đơn đã được tạo', 'id': invoice_id}), 201
    except Exception as e:
        conn.close()
        return jsonify({'message': str(e)}), 500

@invoices_bp.route('/api/invoices/<int:id>', methods=['PUT'])
def update_invoice(id):
    ensure_invoices_table()
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM invoices WHERE id = ?", (id,))
    invoice = c.fetchone()
    if not invoice:
        conn.close()
        return jsonify({'message': 'Hóa đơn không tồn tại'}), 404

    invoice_date = datetime.strptime(invoice['date'], '%Y-%m-%d')
    current_date = datetime.now()
    if (current_date - invoice_date).days > 7:
        conn.close()
        return jsonify({'message': 'Chỉ có thể sửa hóa đơn trong vòng 1 tuần gần nhất'}), 403

    data = request.form
    date = data.get('date', invoice['date'])
    type_ = data.get('type', invoice['type'])
    purpose = data.get('purpose', invoice['purpose'])
    total = float(data.get('total', invoice['total']))
    discount = float(data.get('discount', invoice['discount']))
    discount_type = data.get('discount_type', invoice['discount_type'])
    items = data.get('items', invoice['items'])
    note = data.get('note', invoice['note'])

    if not all([date, type_, items]):
        conn.close()
        return jsonify({'message': 'Thiếu thông tin bắt buộc'}), 400

    if type_ == 'Xuất' and not purpose:
        conn.close()
        return jsonify({'message': 'Hóa đơn xuất cần có mục đích'}), 400

    try:
        items_list = json.loads(items) if items else []
        if not items_list:
            conn.close()
            return jsonify({'message': 'Danh sách sản phẩm không được để trống'}), 400

        old_items = json.loads(invoice['items'])
        for item in old_items:
            product_id = item.get('id')
            quantity = int(item.get('quantity', 0))
            if invoice['type'] == 'Nhập':
                c.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (quantity, product_id))
            elif invoice['type'] == 'Xuất':
                c.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (quantity, product_id))

        if type_ == 'Xuất':
            for item in items_list:
                product_id = item.get('id')
                quantity = int(item.get('quantity', 0))
                c.execute("SELECT quantity FROM products WHERE id = ?", (product_id,))
                product = c.fetchone()
                if not product:
                    conn.close()
                    return jsonify({'message': f'Sản phẩm ID {product_id} không tồn tại'}), 404
                current_quantity = product['quantity']
                if quantity > current_quantity:
                    conn.close()
                    return jsonify({'message': f'Số lượng xuất ({quantity}) của sản phẩm ID {product_id} vượt quá số lượng tồn kho ({current_quantity})'}), 400

        c.execute('''UPDATE invoices SET date = ?, type = ?, purpose = ?, total = ?, discount = ?, discount_type = ?, items = ?, note = ?
                     WHERE id = ?''',
                  (date, type_, purpose, total, discount, discount_type, items, note, id))

        for item in items_list:
            product_id = item.get('id')
            quantity = int(item.get('quantity', 0))
            if type_ == 'Nhập':
                c.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (quantity, product_id))
            elif type_ == 'Xuất':
                c.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (quantity, product_id))

        conn.commit()
        conn.close()
        return jsonify({'message': 'Hóa đơn đã được cập nhật'}), 200
    except Exception as e:
        conn.close()
        return jsonify({'message': str(e)}), 500

@invoices_bp.route('/api/invoices/<int:id>', methods=['DELETE'])
def delete_invoice(id):
    ensure_invoices_table()
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM invoices WHERE id = ?", (id,))
    invoice = c.fetchone()
    if not invoice:
        conn.close()
        return jsonify({'message': 'Hóa đơn không tồn tại'}), 404

    invoice_date = datetime.strptime(invoice['date'], '%Y-%m-%d')
    current_date = datetime.now()
    if (current_date - invoice_date).days > 7:
        conn.close()
        return jsonify({'message': 'Chỉ có thể xóa hóa đơn trong vòng 1 tuần gần nhất'}), 403

    try:
        items = json.loads(invoice['items'])
        for item in items:
            product_id = item.get('id')
            quantity = int(item.get('quantity', 0))
            if invoice['type'] == 'Nhập':
                c.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (quantity, product_id))
            elif invoice['type'] == 'Xuất':
                c.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (quantity, product_id))

        c.execute("DELETE FROM invoices WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Hóa đơn đã được xóa'}), 200
    except Exception as e:
        conn.close()
        return jsonify({'message': str(e)}), 500