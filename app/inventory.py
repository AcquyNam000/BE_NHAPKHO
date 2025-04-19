from flask import Blueprint, request, jsonify, render_template
from .database import get_db_connection
import sqlite3

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/inventory', methods=['GET'])
def inventory_page():
    return render_template('inventory.html')

@inventory_bp.route('/api/inventory', methods=['GET'])
def get_inventory():
    search = request.args.get('search', '')

    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Lấy danh sách sản phẩm từ bảng products
        query = '''
            SELECT p.id, p.name, p.unit, p.purchase_price, p.selling_price, p.quantity
            FROM products p
            WHERE 1=1
        '''
        params = []
        if search:
            query += " AND (p.name LIKE ?)"
            params.append(f'%{search}%')

        c.execute(query, params)
        products = c.fetchall()

        # Tạo danh sách sản phẩm tồn kho
        inventory_list = []
        total_value = 0
        total_products = len(products)

        for product in products:
            # Tính tổng giá trị tồn kho (giá nhập * số lượng)
            total_item_value = float(product['purchase_price']) * product['quantity']
            total_value += total_item_value

            # Xác định trạng thái (còn hàng/hết hàng)
            status = "Còn hàng" if product['quantity'] > 0 else "Hết hàng"

            inventory_list.append({
                'id': product['id'],
                'name': product['name'],
                'unit': product['unit'],
                'purchase_price': float(product['purchase_price']),
                'selling_price': float(product['selling_price']),
                'quantity': product['quantity'],
                'total_value': total_item_value,
                'status': status,
                'note': ''  # Ghi chú có thể để trống hoặc lấy từ dữ liệu khác nếu cần
            })

        return jsonify({
            'inventory': inventory_list,
            'total_products': total_products,
            'total_value': total_value
        })
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()