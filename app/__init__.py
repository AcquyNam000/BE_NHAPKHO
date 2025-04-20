from flask import Flask, render_template
from .database import init_db, get_db_connection
from .products import products_bp
from .invoices import invoices_bp
from .reports import reports_bp
from app.inventory import inventory_bp
from app.dashboard import dashboard_bp
from .statistics import statistics_bp
import os
from app.revenue import revenue_bp
def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config.from_object('config.Config')

    # Kiểm tra và khởi tạo cơ sở dữ liệu nếu không tồn tại
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'inventory.db')
    if not os.path.exists(db_path):
        init_db()

    # Kiểm tra bảng products
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
        if not c.fetchone():
            init_db()
        conn.close()
    except Exception as e:
        print(f"Error checking database: {e}")
        init_db()

    # Đăng ký các blueprint
    app.register_blueprint(products_bp)
    app.register_blueprint(invoices_bp)
    # app.register_blueprint(reports_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(revenue_bp)
    app.register_blueprint(statistics_bp)

    # Route cho trang chính
    @app.route('/')
    def dashboard():
        return render_template('dashboard.html')

    return app