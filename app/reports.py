from flask import Blueprint, jsonify, request, render_template
from .database import get_db_connection

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/inventory', methods=['GET'])
def inventory_page():
    return render_template('inventory.html')

@reports_bp.route('/inventory', methods=['GET'])
def get_inventory():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    offset = (page - 1) * per_page

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    total = len(c.fetchall())
    c.execute("SELECT * FROM products LIMIT ? OFFSET ?", (per_page, offset))
    products = c.fetchall()
    conn.close()

    inventory = []
    for p in products:
        total_value = p['selling_price'] * p['quantity']
        status = 'Còn hàng' if p['quantity'] > 10 else 'Sắp hết' if p['quantity'] > 0 else 'Hết hàng'
        inventory.append({
            'id': p['id'],
            'code': p['code'],
            'name': p['name'],
            'unit': p['unit'],
            'purchase_price': p['purchase_price'],
            'selling_price': p['selling_price'],
            'quantity': p['quantity'],
            'total_value': total_value,
            'status': status,
            'note': p['note']
        })

    return jsonify({
        'inventory': inventory,
        'total_items': len(inventory),
        'total_value': sum(item['total_value'] for item in inventory),
        'total_pages': (total + per_page - 1) // per_page
    }), 200

@reports_bp.route('/sales/total', methods=['GET'])
def sales_page():
    return render_template('sales.html')

@reports_bp.route('/sales/total', methods=['GET'])
def get_sales_total():
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT SUM(total) as total FROM invoices WHERE type = 'SELL'"
    params = []
    if start_date and end_date:
        query += " AND date BETWEEN ? AND ?"
        params.extend([start_date + ' 00:00:00', end_date + ' 23:59:59'])
    
    c.execute(query, params)
    result = c.fetchone()
    conn.close()

    return jsonify({
        'total_sales': result['total'] or 0
    }), 200