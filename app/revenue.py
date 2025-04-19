from flask import Blueprint, request, jsonify, render_template
from .database import get_db_connection

revenue_bp = Blueprint('revenue', __name__)

@revenue_bp.route('/revenue', methods=['GET'])
def revenue_page():
    return render_template('revenue.html')

@revenue_bp.route('/api/revenue', methods=['GET'])
def get_revenue():
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Truy vấn tổng tiền nhập và doanh thu theo từng tháng
        query = '''
            SELECT strftime('%Y-%m', date) as month,
                   SUM(CASE WHEN type = 'Nhập' THEN total ELSE 0 END) as total_import,
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

        query += " GROUP BY strftime('%Y-%m', date) ORDER BY month DESC"
        c.execute(query, params)
        rows = c.fetchall()

        # Tạo danh sách báo cáo
        revenue_list = []
        for row in rows:
            total_import = float(row['total_import'] or 0)
            total_export = float(row['total_export'] or 0)
            profit = total_export - total_import  # Lợi nhuận = Doanh thu - Chi phí nhập

            revenue_list.append({
                'month': row['month'],
                'total_import': total_import,
                'total_export': total_export,
                'profit': profit
            })

        return jsonify({'revenue': revenue_list})
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    finally:
        conn.close()