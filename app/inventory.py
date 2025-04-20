from flask import Blueprint, request, jsonify, render_template, send_file
from .database import get_db_connection
import sqlite3
import pandas as pd
from io import BytesIO
import os
import logging

# Thiết lập logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

inventory_bp = Blueprint('inventory', __name__)

def ensure_products_table():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Kiểm tra và tạo bảng products nếu chưa tồn tại
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
    if not c.fetchone():
        c.execute('''CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            unit TEXT NOT NULL,
            purchase_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            image TEXT
        )''')
    else:
        # Kiểm tra và thêm cột image nếu chưa có
        c.execute("PRAGMA table_info(products)")
        columns = [col[1] for col in c.fetchall()]
        if 'image' not in columns:
            c.execute("ALTER TABLE products ADD COLUMN image TEXT")
    
    conn.commit()
    conn.close()

@inventory_bp.route('/inventory', methods=['GET'])
def inventory_page():
    ensure_products_table()
    return render_template('inventory.html')

@inventory_bp.route('/api/inventory', methods=['GET'])
def get_inventory():
    ensure_products_table()
    search = request.args.get('search', '')

    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Lấy danh sách sản phẩm từ bảng products, bao gồm cột image
        query = '''
            SELECT p.id, p.name, p.unit, p.purchase_price, p.selling_price, p.quantity, p.image
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

            # Chuẩn hóa đường dẫn ảnh
            image_path = product['image']
            logger.debug(f"Original image path for product {product['id']}: {image_path}")
            if image_path and image_path.strip() != '':
                # Loại bỏ phần /static/ khỏi đường dẫn để kiểm tra file trong thư mục static/
                relative_path = image_path.lstrip('/static/') if image_path.startswith('/static/') else image_path.lstrip('/')
                static_path = os.path.join('static', relative_path).replace('/', os.sep)
                logger.debug(f"Checking file existence at: {static_path}")
                # Kiểm tra xem file ảnh có tồn tại không
                if os.path.exists(static_path):
                    image_url = image_path
                    logger.debug(f"Image found for product {product['id']}: {image_url}")
                else:
                    logger.debug(f"Image file not found for product {product['id']}: {static_path}")
                    image_url = None  # Nếu file không tồn tại, trả về null
            else:
                image_url = None  # Nếu image rỗng hoặc NULL, trả về null
                logger.debug(f"No image path for product {product['id']}")

            inventory_list.append({
                'id': product['id'],
                'name': product['name'],
                'unit': product['unit'],
                'purchase_price': float(product['purchase_price']),
                'selling_price': float(product['selling_price']),
                'quantity': product['quantity'],
                'total_value': total_item_value,
                'status': status,
                'note': '',  # Ghi chú để trống vì không có trong bảng products
                'image': image_url  # Trả về đường dẫn hợp lệ hoặc null
            })

        return jsonify({
            'inventory': inventory_list,
            'total_products': total_products,
            'total_value': total_value
        })
    except Exception as e:
        logger.error(f"Error in get_inventory: {str(e)}")
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()

@inventory_bp.route('/api/inventory/export/excel', methods=['GET'])
def export_excel():
    try:
        ensure_products_table()
        search = request.args.get('search', '')

        conn = get_db_connection()
        c = conn.cursor()

        # Lấy danh sách sản phẩm từ bảng products để xuất Excel
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

        if not products:
            return jsonify({'message': 'Không có sản phẩm nào để xuất'}), 404

        # Tạo dữ liệu cho file Excel
        data = []
        for product in products:
            total_item_value = float(product['purchase_price']) * product['quantity']
            status = "Còn hàng" if product['quantity'] > 0 else "Hết hàng"
            data.append({
                'Mã': product['id'],
                'Tên': product['name'],
                'Đơn vị': product['unit'],
                'Giá nhập': float(product['purchase_price']),
                'Giá bán': float(product['selling_price']),
                'Số lượng': int(product['quantity']),
                'Tổng giá trị': total_item_value,
                'Trạng thái': status,
                'Ghi chú': ''
            })

        # Tạo file Excel
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Inventory')
            workbook = writer.book
            worksheet = writer.sheets['Inventory']
            number_format = workbook.add_format({'num_format': '#,##0'})
            worksheet.set_column('D:D', None, number_format)  # Cột Giá nhập
            worksheet.set_column('E:E', None, number_format)  # Cột Giá bán
            worksheet.set_column('G:G', None, number_format)  # Cột Tổng giá trị
        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name='inventory.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except ImportError as e:
        return jsonify({'message': f'Lỗi khi xuất Excel: Vui lòng cài đặt thư viện xlsxwriter: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'message': f'Lỗi khi xuất Excel: {str(e)}'}), 500
    finally:
        conn.close()