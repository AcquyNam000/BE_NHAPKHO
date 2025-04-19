// Hàm định dạng tiền tệ
function formatCurrency(number) {
    if (typeof number !== 'number' || isNaN(number)) {
        return '0 VNĐ';
    }
    return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ' VNĐ';
}

// Products
function searchProducts() {
    const searchInput = document.getElementById('search');
    const tbody = document.querySelector('#product-table tbody');
    const pageInfo = document.getElementById('page-info');

    if (!searchInput || !tbody || !pageInfo) {
        console.error('Không tìm thấy phần tử DOM cần thiết cho searchProducts');
        return;
    }

    const search = searchInput.value;
    const page = parseInt(pageInfo.textContent.split(' ')[1]) || 1;
    fetch(`/api/products?search=${encodeURIComponent(search)}&page=${page}`, {
        headers: {
            'Accept': 'application/json'
        }
    })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(`HTTP error! Status: ${response.status}, Response: ${text}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Dữ liệu trả về từ /api/products:', JSON.stringify(data, null, 2));
            tbody.innerHTML = '';

            if (!data || typeof data !== 'object') {
                throw new Error('Phản hồi không phải JSON hợp lệ');
            }
            if (!data.products) {
                throw new Error('Dữ liệu thiếu trường "products"');
            }

            if (data.products.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8">Không có sản phẩm nào</td></tr>';
                pageInfo.textContent = 'Trang 1 / 1';
                return;
            }

            data.products.forEach(p => {
                if (!p.id || !p.code || !p.name) {
                    console.warn('Sản phẩm không hợp lệ:', p);
                    return;
                }
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${p.code || ''}</td>
                    <td>${p.name || ''}</td>
                    <td>${p.unit || ''}</td>
                    <td>${formatCurrency(p.purchase_price)}</td>
                    <td>${formatCurrency(p.selling_price)}</td>
                    <td>${p.image ? `<img src="${p.image}" width="50" alt="Hình ảnh sản phẩm">` : ''}</td>
                    <td>${p.note || ''}</td>
                    <td>
                        <button onclick="editProduct(${p.id})">Sửa</button>
                        <button onclick="deleteProduct(${p.id})">Xóa</button>
                    </td>
                `;
                tbody.appendChild(row);
            });
            pageInfo.textContent = `Trang ${data.page || 1} / ${Math.ceil((data.total || 0) / (data.per_page || 10))}`;
        })
        .catch(error => {
            console.error('Lỗi khi tải sản phẩm:', error.message);
            tbody.innerHTML = '<tr><td colspan="8">Không thể tải danh sách sản phẩm. Vui lòng thử lại sau.</td></tr>';
        });
}

function prevPage() {
    const pageInfo = document.getElementById('page-info');
    const searchInput = document.getElementById('search');
    if (!pageInfo || !searchInput) return;

    const currentPage = parseInt(pageInfo.textContent.split(' ')[1]) || 1;
    if (currentPage > 1) {
        const search = searchInput.value;
        fetch(`/api/products?page=${currentPage - 1}&search=${encodeURIComponent(search)}`, {
            headers: {
                'Accept': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                return response.json();
            })
            .then(() => searchProducts())
            .catch(error => console.error('Lỗi khi chuyển trang:', error));
    }
}

function nextPage() {
    const pageInfo = document.getElementById('page-info');
    const searchInput = document.getElementById('search');
    if (!pageInfo || !searchInput) return;

    const currentPage = parseInt(pageInfo.textContent.split(' ')[1]) || 1;
    const totalPages = parseInt(pageInfo.textContent.split(' ')[3]) || 1;
    if (currentPage < totalPages) {
        const search = searchInput.value;
        fetch(`/api/products?page=${currentPage + 1}&search=${encodeURIComponent(search)}`, {
            headers: {
                'Accept': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                return response.json();
            })
            .then(() => searchProducts())
            .catch(error => console.error('Lỗi khi chuyển trang:', error));
    }
}

function exportExcel() {
    window.location.href = '/api/products/export/excel';
}

function editProduct(id) {
    alert('Chức năng sửa sản phẩm chưa được triển khai');
}

function deleteProduct(id) {
    if (confirm('Bạn có chắc muốn xóa sản phẩm này?')) {
        fetch(`/api/products/${id}`, {
            method: 'DELETE',
            headers: {
                'Accept': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                alert(data.message);
                searchProducts();
            })
            .catch(error => console.error('Lỗi khi xóa sản phẩm:', error));
    }
}

// Xử lý form thêm sản phẩm
document.addEventListener('DOMContentLoaded', () => {
    const productForm = document.getElementById('product-form');
    if (productForm) {
        productForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const formData = new FormData(productForm);
            try {
                const response = await fetch('/api/products', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                const data = await response.json();
                if (response.ok) {
                    alert(data.message);
                    productForm.reset();
                    searchProducts();
                } else {
                    alert(data.message);
                }
            } catch (error) {
                console.error('Lỗi khi thêm sản phẩm:', error);
                alert('Lỗi khi thêm sản phẩm. Vui lòng thử lại.');
            }
        });
    }

    // Khởi tạo các trang
    try {
        if (document.getElementById('product-table')) searchProducts();
        if (document.getElementById('invoice-table')) searchInvoices();
        if (document.getElementById('inventory-table')) searchInventory();
    } catch (error) {
        console.error('Lỗi khi khởi tạo trang:', error);
    }
});

// Invoices
async function searchInvoices() {
    const searchInput = document.getElementById('search');
    const tbody = document.querySelector('#invoice-table tbody');
    const pageInfo = document.getElementById('invoice-page-info');

    if (!searchInput || !tbody || !pageInfo) {
        console.error('Không tìm thấy phần tử DOM cần thiết cho searchInvoices');
        return;
    }

    const search = searchInput.value;
    fetch(`/api/invoices?search=${encodeURIComponent(search)}`, {
        headers: {
            'Accept': 'application/json'
        }
    })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(`HTTP error! Status: ${response.status}, Response: ${text}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Dữ liệu trả về từ /api/invoices:', JSON.stringify(data, null, 2));
            tbody.innerHTML = '';
            if (!data.invoices) {
                throw new Error('Dữ liệu thiếu trường "invoices"');
            }
            if (data.invoices.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8">Không có hóa đơn nào</td></tr>';
                pageInfo.textContent = 'Trang 1 / 1';
                return;
            }
            data.invoices.forEach(i => {
                // Chuyển đổi items từ JSON thành danh sách tên sản phẩm
                let itemsList = [];
                try {
                    const items = JSON.parse(i.items || '[]');
                    itemsList = items.map(item => {
                        const productName = item.name || `Sản phẩm ${item.id}`;
                        return `${productName} (${item.quantity})`;
                    });
                } catch (e) {
                    console.error('Lỗi khi parse items:', e);
                    itemsList = ['Dữ liệu lỗi'];
                }
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${i.id || ''}</td>
                    <td>${i.date || ''}</td>
                    <td>${i.type || ''}</td>
                    <td>${i.purpose || ''}</td>
                    <td>${formatCurrency(i.total)}</td>
                    <td>${formatCurrency(i.discount)}</td>
                    <td>${itemsList.join(', ')}</td>
                    <td>${i.note || ''}</td>
                `;
                tbody.appendChild(row);
            });
            pageInfo.textContent = `Trang ${data.page || 1} / ${Math.ceil((data.total || 0) / (data.per_page || 10))}`;
        })
        .catch(error => {
            console.error('Lỗi khi tải hóa đơn:', error.message);
            tbody.innerHTML = '<tr><td colspan="8">Không thể tải danh sách hóa đơn. Vui lòng thử lại sau.</td></tr>';
        });
}

function prevInvoicePage() {
    const pageInfo = document.getElementById('invoice-page-info');
    if (!pageInfo) return;

    const currentPage = parseInt(pageInfo.textContent.split(' ')[1]) || 1;
    if (currentPage > 1) {
        fetch(`/api/invoices?page=${currentPage - 1}`, {
            headers: {
                'Accept': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                return response.json();
            })
            .then(() => searchInvoices())
            .catch(error => console.error('Lỗi khi chuyển trang hóa đơn:', error));
    }
}

function nextInvoicePage() {
    const pageInfo = document.getElementById('invoice-page-info');
    if (!pageInfo) return;

    const currentPage = parseInt(pageInfo.textContent.split(' ')[1]) || 1;
    fetch(`/api/invoices?page=${currentPage + 1}`, {
        headers: {
            'Accept': 'application/json'
        }
    })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            return response.json();
        })
        .then(() => searchInvoices())
        .catch(error => console.error('Lỗi khi chuyển trang hóa đơn:', error));
}

// Inventory
function searchInventory() {
    const searchInput = document.getElementById('search');
    const tbody = document.querySelector('#inventory-table tbody');
    const pageInfo = document.getElementById('inventory-page-info');
    const totalItems = document.getElementById('total-items');
    const totalValue = document.getElementById('total-value');

    if (!searchInput || !tbody || !pageInfo || !totalItems || !totalValue) {
        console.error('Không tìm thấy phần tử DOM cần thiết cho searchInventory');
        return;
    }

    const search = searchInput.value;
    fetch(`/inventory?search=${encodeURIComponent(search)}`, {
        headers: {
            'Accept': 'application/json'
        }
    })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(`HTTP error! Status: ${response.status}, Response: ${text}`);
                });
            }
            return response.json();
        })
        .then(data => {
            tbody.innerHTML = '';
            if (!data.inventory) {
                throw new Error('Dữ liệu thiếu trường "inventory"');
            }
            data.inventory.forEach(item => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${item.code || ''}</td>
                    <td>${item.name || ''}</td>
                    <td>${item.unit || ''}</td>
                    <td>${formatCurrency(item.purchase_price)}</td>
                    <td>${formatCurrency(item.selling_price)}</td>
                    <td>${item.quantity || 0}</td>
                    <td>${formatCurrency(item.total_value)}</td>
                    <td>${item.status || ''}</td>
                    <td>${item.note || ''}</td>
                `;
                tbody.appendChild(row);
            });
            pageInfo.textContent = `Trang ${data.page || 1} / ${data.total_pages || 1}`;
            totalItems.textContent = data.total_items || 0;
            totalValue.textContent = formatCurrency(data.total_value);
        })
        .catch(error => {
            console.error('Lỗi khi tải kho:', error.message);
            tbody.innerHTML = '<tr><td colspan="9">Không thể tải danh sách kho. Vui lòng thử lại sau.</td></tr>';
        });
}

function prevInventoryPage() {
    const pageInfo = document.getElementById('inventory-page-info');
    if (!pageInfo) return;

    const currentPage = parseInt(pageInfo.textContent.split(' ')[1]) || 1;
    if (currentPage > 1) {
        fetch(`/inventory?page=${currentPage - 1}`, {
            headers: {
                'Accept': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                return response.json();
            })
            .then(() => searchInventory())
            .catch(error => console.error('Lỗi khi chuyển trang kho:', error));
    }
}

function nextInventoryPage() {
    const pageInfo = document.getElementById('inventory-page-info');
    if (!pageInfo) return;

    const currentPage = parseInt(pageInfo.textContent.split(' ')[1]) || 1;
    fetch(`/inventory?page=${currentPage + 1}`, {
        headers: {
            'Accept': 'application/json'
        }
    })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            return response.json();
        })
        .then(() => searchInventory())
        .catch(error => console.error('Lỗi khi chuyển trang kho:', error));
}

// Sales
function loadSales() {
    const startDateInput = document.getElementById('start-date');
    const endDateInput = document.getElementById('end-date');
    const totalSales = document.getElementById('total-sales');

    if (!startDateInput || !endDateInput || !totalSales) {
        console.error('Không tìm thấy phần tử DOM cần thiết cho loadSales');
        return;
    }

    const startDate = startDateInput.value;
    const endDate = endDateInput.value;
    fetch(`/sales/total?start_date=${startDate}&end_date=${end_date}`, {
        headers: {
            'Accept': 'application/json'
        }
    })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(`HTTP error! Status: ${response.status}, Response: ${text}`);
                });
            }
            return response.json();
        })
        .then(data => {
            totalSales.textContent = formatCurrency(data.total_sales);
        })
        .catch(error => console.error('Lỗi khi tải doanh thu:', error));
}