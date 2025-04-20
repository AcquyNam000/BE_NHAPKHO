from flask import Blueprint, request, jsonify, render_template, send_file
from .database import get_db_connection
import sqlite3
import os
from werkzeug.utils import secure_filename
import pandas as pd
from io import BytesIO

products_bp = Blueprint('products', __name__)

UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_products_table():
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Kiểm tra và tạo bảng products nếu chưa tồn tại
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
        if not c.fetchone():
            c.execute('''CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                name TEXT NOT NULL,
                unit TEXT,
                purchase_price REAL NOT NULL,
                selling_price REAL NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                image TEXT,
                note TEXT
            )''')
        else:
            # Kiểm tra và thêm cột image nếu chưa có
            c.execute("PRAGMA table_info(products)")
            columns = [col[1] for col in c.fetchall()]
            if 'image' not in columns:
                c.execute("ALTER TABLE products ADD COLUMN image TEXT")
            # Kiểm tra và thêm cột quantity nếu chưa có
            if 'quantity' not in columns:
                c.execute("ALTER TABLE products ADD COLUMN quantity INTEGER NOT NULL DEFAULT 0")
            else:
                # Nếu cột quantity đã tồn tại nhưng không có giá trị mặc định, cập nhật các giá trị NULL thành 0
                c.execute("UPDATE products SET quantity = 0 WHERE quantity IS NULL")
            # Đảm bảo cột code có ràng buộc UNIQUE
            try:
                c.execute("CREATE UNIQUE INDEX idx_products_code ON products(code)")
            except sqlite3.OperationalError:
                pass  # Chỉ số đã tồn tại

        conn.commit()
    except sqlite3.OperationalError as e:
        raise Exception(f"Lỗi khi đảm bảo cấu trúc bảng: {str(e)}")
    finally:
        if conn:
            conn.close()

@products_bp.route('/products', methods=['GET'])
def products_page():
    try:
        ensure_products_table()
        return render_template('products.html')
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@products_bp.route('/api/products', methods=['GET'])
def get_products():
    try:
        ensure_products_table()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        search = request.args.get('search', '')
        product_id = request.args.get('id', '')
        offset = (page - 1) * per_page

        conn = get_db_connection()
        c = conn.cursor()

        try:
            query = "SELECT id, code, name, unit, purchase_price, selling_price, quantity, image, note FROM products WHERE 1=1"
            params = []
            if search:
                query += " AND (code LIKE ? OR name LIKE ?)"
                params.extend([f'%{search}%', f'%{search}%'])
            if product_id:
                query += " AND id = ?"
                params.append(product_id)

            # Đếm tổng số sản phẩm trước khi phân trang
            c.execute(query, params)
            total = len(c.fetchall())

            # Thêm ORDER BY và LIMIT để phân trang
            query += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([per_page, offset])

            c.execute(query, params)
            products = c.fetchall()

            products_list = []
            for product in products:
                products_list.append({
                    'id': product['id'],
                    'code': product['code'],
                    'name': product['name'],
                    'unit': product['unit'],
                    'purchase_price': float(product['purchase_price']),
                    'selling_price': float(product['selling_price']),
                    'quantity': product['quantity'],
                    'image': product['image'],
                    'note': product['note']
                })

            return jsonify({
                'products': products_list,
                'page': page,
                'per_page': per_page,
                'total': total
            })
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@products_bp.route('/api/products/search', methods=['GET'])
def search_products():
    try:
        ensure_products_table()
        query = request.args.get('q', '')
        conn = get_db_connection()
        c = conn.cursor()

        try:
            c.execute("SELECT id, code, name, unit, purchase_price, selling_price, quantity, image, note FROM products WHERE name LIKE ? LIMIT 10", (f'%{query}%',))
            products = c.fetchall()

            suggestions = []
            for product in products:
                suggestions.append({
                    'id': product['id'],
                    'code': product['code'],
                    'name': product['name'],
                    'unit': product['unit'],
                    'purchase_price': float(product['purchase_price']),
                    'selling_price': float(product['selling_price']),
                    'quantity': product['quantity'],
                    'image': product['image'],
                    'note': product['note']
                })

            return jsonify(suggestions)
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@products_bp.route('/api/products', methods=['POST'])
def create_product():
    try:
        ensure_products_table()
        code = request.form.get('code')
        name = request.form.get('name')
        unit = request.form.get('unit')
        purchase_price = request.form.get('purchase_price')
        selling_price = request.form.get('selling_price')
        note = request.form.get('note')
        image = request.files.get('image')

        if not all([name, purchase_price, selling_price]):
            return jsonify({'message': 'Thiếu thông tin bắt buộc'}), 400

        # Tạo thư mục lưu trữ hình ảnh nếu chưa tồn tại
        os.makedirs(os.path.join('app', UPLOAD_FOLDER), exist_ok=True)

        image_path = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image_path = f"/{UPLOAD_FOLDER}/{filename}"
            try:
                image.save(os.path.join('app', UPLOAD_FOLDER, filename))
            except Exception as e:
                return jsonify({'message': f'Lỗi khi lưu hình ảnh: {str(e)}'}), 500

        purchase_price = float(purchase_price)
        selling_price = float(selling_price)
        if purchase_price < 0 or selling_price < 0:
            return jsonify({'message': 'Giá nhập và giá bán phải lớn hơn hoặc bằng 0'}), 400

        conn = get_db_connection()
        c = conn.cursor()

        try:
            c.execute('''INSERT INTO products (code, name, unit, purchase_price, selling_price, image, note, quantity)
                         VALUES (?, ?, ?, ?, ?, ?, ?, 0)''',
                      (code, name, unit, purchase_price, selling_price, image_path, note))
            conn.commit()
            return jsonify({'message': 'Sản phẩm đã được tạo'}), 201
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                return jsonify({'message': 'Mã sản phẩm đã tồn tại. Vui lòng chọn mã khác.'}), 400
            raise
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'message': f'Lỗi khi thêm sản phẩm: {str(e)}'}), 500

@products_bp.route('/api/products/<int:id>', methods=['PUT'])
def update_product(id):
    try:
        ensure_products_table()
        conn = get_db_connection()
        c = conn.cursor()

        try:
            # Lấy thông tin sản phẩm hiện tại
            c.execute("SELECT * FROM products WHERE id = ?", (id,))
            product = c.fetchone()
            if not product:
                return jsonify({'message': 'Sản phẩm không tồn tại'}), 404

            code = request.form.get('code', product['code'])
            name = request.form.get('name', product['name'])
            unit = request.form.get('unit', product['unit'])
            purchase_price = request.form.get('purchase_price', product['purchase_price'])
            selling_price = request.form.get('selling_price', product['selling_price'])
            note = request.form.get('note', product['note'])
            image = request.files.get('image')

            if not all([name, purchase_price, selling_price]):
                return jsonify({'message': 'Thiếu thông tin bắt buộc'}), 400

            # Kiểm tra xem mã sản phẩm mới có trùng với sản phẩm khác không
            if code != product['code']:  # Chỉ kiểm tra nếu mã thay đổi
                c.execute("SELECT id FROM products WHERE code = ? AND id != ?", (code, id))
                if c.fetchone():
                    return jsonify({'message': 'Mã sản phẩm đã tồn tại. Vui lòng chọn mã khác.'}), 400

            image_path = product['image']
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image_path = f"/{UPLOAD_FOLDER}/{filename}"
                try:
                    image.save(os.path.join('app', UPLOAD_FOLDER, filename))
                except Exception as e:
                    return jsonify({'message': f'Lỗi khi lưu hình ảnh: {str(e)}'}), 500

            purchase_price = float(purchase_price)
            selling_price = float(selling_price)
            if purchase_price < 0 or selling_price < 0:
                return jsonify({'message': 'Giá nhập và giá bán phải lớn hơn hoặc bằng 0'}), 400

            c.execute('''UPDATE products SET code = ?, name = ?, unit = ?, purchase_price = ?, selling_price = ?, image = ?, note = ?
                         WHERE id = ?''',
                      (code, name, unit, purchase_price, selling_price, image_path, note, id))
            conn.commit()
            return jsonify({'message': 'Sản phẩm đã được cập nhật'}), 200
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                return jsonify({'message': 'Mã sản phẩm đã tồn tại. Vui lòng chọn mã khác.'}), 400
            raise
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@products_bp.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    try:
        ensure_products_table()
        conn = get_db_connection()
        c = conn.cursor()

        try:
            c.execute("SELECT * FROM products WHERE id = ?", (id,))
            product = c.fetchone()
            if not product:
                return jsonify({'message': 'Sản phẩm không tồn tại'}), 404

            c.execute("DELETE FROM products WHERE id = ?", (id,))
            conn.commit()
            return jsonify({'message': 'Sản phẩm đã được xóa'}), 200
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@products_bp.route('/api/products/export/excel', methods=['GET'])
def export_excel():
    try:
        ensure_products_table()
        conn = get_db_connection()
        c = conn.cursor()

        try:
            c.execute("SELECT code, name, unit, purchase_price, selling_price, image, note FROM products")
            products = c.fetchall()

            if not products:
                return jsonify({'message': 'Không có dữ liệu để xuất Excel'}), 404

            data = []
            for product in products:
                data.append({
                    'Mã': product['code'] if product['code'] else '',
                    'Tên': product['name'],
                    'Đơn vị': product['unit'] if product['unit'] else '',
                    'Giá nhập': float(product['purchase_price']),
                    'Giá bán': float(product['selling_price']),
                    'Hình ảnh': product['image'] if product['image'] else '',
                    'Ghi chú': product['note'] if product['note'] else ''
                })

            df = pd.DataFrame(data)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Products')
                workbook = writer.book
                worksheet = writer.sheets['Products']
                number_format = workbook.add_format({'num_format': '#,##0'})
                worksheet.set_column('D:D', None, number_format)  # Cột Giá nhập
                worksheet.set_column('E:E', None, number_format)  # Cột Giá bán
            output.seek(0)

            return send_file(
                output,
                as_attachment=True,
                download_name='products.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        finally:
            conn.close()
    except ImportError as e:
        return jsonify({'message': f'Lỗi khi xuất Excel: Vui lòng cài đặt thư viện xlsxwriter: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'message': f'Lỗi khi xuất Excel: {str(e)}'}), 500

@products_bp.route('/api/products/import/excel', methods=['POST'])
def import_excel():
    try:
        ensure_products_table()

        # Kiểm tra xem có file được tải lên không
        if 'file' not in request.files:
            return jsonify({'message': 'Không có file được tải lên'}), 400

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'message': 'File không hợp lệ'}), 400

        # Kiểm tra định dạng file
        if not file.filename.endswith('.xlsx'):
            return jsonify({'message': 'Chỉ hỗ trợ file Excel (.xlsx)'}), 400

        # Đọc file Excel
        df = pd.read_excel(file, sheet_name='Products')

        # Kiểm tra cấu trúc file Excel
        expected_columns = ['Mã', 'Tên', 'Đơn vị', 'Giá nhập', 'Giá bán', 'Hình ảnh', 'Ghi chú']
        if not all(col in df.columns for col in expected_columns):
            return jsonify({'message': 'File Excel không đúng định dạng. Cần có các cột: Mã, Tên, Đơn vị, Giá nhập, Giá bán, Hình ảnh, Ghi chú'}), 400

        conn = get_db_connection()
        c = conn.cursor()

        try:
            imported_count = 0
            updated_count = 0

            for _, row in df.iterrows():
                code = str(row['Mã']) if pd.notna(row['Mã']) else None
                name = str(row['Tên']) if pd.notna(row['Tên']) else ''
                unit = str(row['Đơn vị']) if pd.notna(row['Đơn vị']) else None
                purchase_price = float(row['Giá nhập']) if pd.notna(row['Giá nhập']) else 0.0
                selling_price = float(row['Giá bán']) if pd.notna(row['Giá bán']) else 0.0
                image = str(row['Hình ảnh']) if pd.notna(row['Hình ảnh']) else None
                note = str(row['Ghi chú']) if pd.notna(row['Ghi chú']) else None

                # Kiểm tra xem sản phẩm đã tồn tại chưa (dựa trên code)
                c.execute("SELECT id FROM products WHERE code = ?", (code,))
                existing_product = c.fetchone()

                if existing_product:
                    # Cập nhật sản phẩm nếu mã đã tồn tại
                    c.execute('''UPDATE products SET name = ?, unit = ?, purchase_price = ?, selling_price = ?, image = ?, note = ?
                                 WHERE code = ?''',
                              (name, unit, purchase_price, selling_price, image, note, code))
                    updated_count += 1
                else:
                    # Thêm sản phẩm mới
                    c.execute('''INSERT INTO products (code, name, unit, purchase_price, selling_price, image, note, quantity)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, 0)''',
                              (code, name, unit, purchase_price, selling_price, image, note))
                    imported_count += 1

            conn.commit()
            return jsonify({
                'message': f'Nhập dữ liệu thành công: {imported_count} sản phẩm được thêm, {updated_count} sản phẩm được cập nhật.'
            }), 200
        finally:
            conn.close()
    except ImportError as e:
        return jsonify({'message': f'Lỗi khi nhập Excel: Vui lòng cài đặt thư viện pandas hoặc openpyxl: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'message': f'Lỗi khi nhập Excel: {str(e)}'}), 500