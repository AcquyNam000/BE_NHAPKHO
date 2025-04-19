from flask import Blueprint, render_template, jsonify
from .database import get_db_connection

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def dashboard_page():
    return render_template('dashboard.html')

@dashboard_bp.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Tổng số sản phẩm (số lượng sản phẩm khác nhau)
        c.execute("SELECT COUNT(*) FROM products")
        total_products = c.fetchone()[0]

        # Tổng số lượng sản phẩm tồn đọng (tổng quantity của các sản phẩm có quantity > 0)
        c.execute("SELECT SUM(quantity) FROM products WHERE quantity > 0")
        total_inventory = c.fetchone()[0] or 0  # Nếu không có sản phẩm nào, trả về 0

        return jsonify({
            'total_products': total_products,
            'total_inventory': total_inventory
        })
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()