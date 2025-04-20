from flask import Blueprint, request, jsonify, render_template
from .database import get_db_connection

statistics_bp = Blueprint('statistics', __name__)

@statistics_bp.route('/statistics', methods=['GET'])
def statistics_page():
    return render_template('statistics.html')

@statistics_bp.route('/api/statistics', methods=['GET'])
def get_statistics():
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Tổng số sản phẩm (số lượng sản phẩm khác nhau)
        c.execute("SELECT COUNT(*) FROM products")
        total_products = c.fetchone()[0]

        # Tổng số lượng sản phẩm tồn đọng (tổng quantity của các sản phẩm có quantity > 0)
        c.execute("SELECT SUM(quantity) FROM products WHERE quantity > 0")
        total_inventory = c.fetchone()[0] or 0

        # Tổng tiền nhập và tổng tiền xuất
        query = '''
            SELECT SUM(CASE WHEN type = 'Nhập' THEN total ELSE 0 END) as total_import,
                   SUM(CASE WHEN type = 'Xuất' THEN total ELSE 0 END) as total_export
            FROM invoices
            WHERE 1=1
        '''
        params = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        c.execute(query, params)
        result = c.fetchone()
        total_import = float(result['total_import'] or 0)
        total_export = float(result['total_export'] or 0)
        profit = total_export - total_import  # Lợi nhuận = Tổng tiền xuất - Tổng tiền nhập

        return jsonify({
            'total_products': total_products,
            'total_inventory': total_inventory,
            'total_import': total_import,
            'total_export': total_export,
            'profit': profit
        })
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()