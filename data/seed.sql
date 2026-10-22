-- Dukaan seed data. Re-running this file is safe: it drops and recreates everything.
-- "Today" when this was written: 2026-10-23.

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS refunds;
DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS orders;

CREATE TABLE orders (
    order_id       INTEGER PRIMARY KEY,
    customer_name  TEXT NOT NULL,
    email          TEXT NOT NULL,
    phone          TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('processing','shipped','delivered','cancelled','returned')),
    amount         REAL NOT NULL,
    payment_method TEXT NOT NULL,
    order_date     TEXT NOT NULL,
    delivery_date  TEXT
);

CREATE TABLE order_items (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id  INTEGER NOT NULL REFERENCES orders(order_id),
    item_name TEXT NOT NULL,
    quantity  INTEGER NOT NULL,
    price     REAL NOT NULL
);

CREATE TABLE refunds (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(order_id),
    amount     REAL NOT NULL,
    reason     TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE tickets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    summary    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO orders (order_id, customer_name, email, phone, status, amount, payment_method, order_date, delivery_date) VALUES
(1041, 'Ananya Sharma',   'ananya.sharma@example.com', '+91 98200 11041', 'delivered',  2499.00, 'UPI',   '2026-10-05', '2026-10-09'),
(1042, 'Rohit Verma',     'rohit.verma@example.com',   '+91 98200 11042', 'delivered',  1299.00, 'Card',  '2026-10-08', '2026-10-11'),
(1043, 'Meera Iyer',      'meera.iyer@example.com',    '+91 98200 11043', 'shipped',     849.00, 'UPI',   '2026-10-19', NULL),
(1044, 'Kabir Singh',     'kabir.singh@example.com',   '+91 98200 11044', 'processing',  399.00, 'COD',   '2026-10-22', NULL),
(1045, 'Priya Nair',      'priya.nair@example.com',    '+91 98200 11045', 'delivered',  5999.00, 'Card',  '2026-09-28', '2026-10-02'),
(1046, 'Arjun Patel',     'arjun.patel@example.com',   '+91 98200 11046', 'cancelled',  1199.00, 'UPI',   '2026-10-14', NULL),
(1047, 'Divya Reddy',     'divya.reddy@example.com',   '+91 98200 11047', 'delivered',   649.00, 'UPI',   '2026-10-16', '2026-10-21'),
(1048, 'Sameer Khan',     'sameer.khan@example.com',   '+91 98200 11048', 'delivered',  8499.00, 'Card',  '2026-10-12', '2026-10-18'),
(1049, 'Nisha Gupta',     'nisha.gupta@example.com',   '+91 98200 11049', 'returned',   1899.00, 'Card',  '2026-09-20', '2026-09-24'),
(1050, 'Vikram Desai',    'vikram.desai@example.com',  '+91 98200 11050', 'shipped',    2199.00, 'COD',   '2026-10-20', NULL),
(1051, 'Fatima Sheikh',   'fatima.sheikh@example.com', '+91 98200 11051', 'delivered',   299.00, 'UPI',   '2026-10-17', '2026-10-20'),
(1052, 'Aditya Rao',      'aditya.rao@example.com',    '+91 98200 11052', 'processing', 3499.00, 'Card',  '2026-10-23', NULL),
(1053, 'Sneha Joshi',     'sneha.joshi@example.com',   '+91 98200 11053', 'delivered',  1749.00, 'UPI',   '2026-10-01', '2026-10-04'),
(1054, 'Imran Qureshi',   'imran.qureshi@example.com', '+91 98200 11054', 'delivered', 12499.00, 'Card',  '2026-10-10', '2026-10-15'),
(1055, 'Lakshmi Menon',   'lakshmi.menon@example.com', '+91 98200 11055', 'cancelled',   549.00, 'UPI',   '2026-10-18', NULL),
(1056, 'Harsh Agarwal',   'harsh.agarwal@example.com', '+91 98200 11056', 'delivered',   999.00, 'COD',   '2026-10-13', '2026-10-17'),
(1057, 'Tanvi Bhatt',     'tanvi.bhatt@example.com',   '+91 98200 11057', 'shipped',    4299.00, 'Card',  '2026-10-21', NULL),
(1058, 'Rahul Mehta',     'rahul.mehta@example.com',   '+91 98200 11058', 'delivered',   459.00, 'UPI',   '2026-08-30', '2026-09-03'),
(1059, 'Zoya Ansari',     'zoya.ansari@example.com',   '+91 98200 11059', 'delivered',  2799.00, 'Card',  '2026-10-15', '2026-10-22'),
(1060, 'Gaurav Thakur',   'gaurav.thakur@example.com', '+91 98200 11060', 'processing',  189.00, 'UPI',   '2026-10-23', NULL);

INSERT INTO order_items (order_id, item_name, quantity, price) VALUES
(1041, 'Cotton Kurta - Indigo, M',          1, 1899.00),
(1041, 'Steel Water Bottle 750ml',          1,  600.00),
(1042, 'Running Shoes - Grey, UK 9',        1, 1299.00),
(1043, 'Ceramic Mug Set (2)',               1,  849.00),
(1044, 'Phone Case - Clear',                1,  399.00),
(1045, 'Wireless Earphones Pro',            1, 5999.00),
(1046, 'Yoga Mat 6mm',                      1, 1199.00),
(1047, 'Masala Chai Blend 250g',            2,  324.50),
(1048, 'Air Fryer 4L',                      1, 8499.00),
(1049, 'Denim Jacket - Blue, L',            1, 1899.00),
(1050, 'Table Lamp - Walnut',               1, 2199.00),
(1051, 'Notebook A5 Dotted',                2,  149.50),
(1052, 'Office Chair - Mesh Back',          1, 3499.00),
(1053, 'Non-stick Pan 24cm',                1, 1249.00),
(1053, 'Silicone Spatula Set',              1,  500.00),
(1054, 'Smartwatch Series 4',               1, 12499.00),
(1055, 'Cushion Cover Pack (4)',            1,  549.00),
(1056, 'Bedsheet - Double, Beige',          1,  999.00),
(1057, 'Backpack 30L - Olive',              1, 2499.00),
(1057, 'Travel Organiser Pouch',            2,  900.00),
(1058, 'Socks Pack (3) - Ankle',            1,  459.00),
(1059, 'Pressure Cooker 3L',                1, 2799.00),
(1060, 'Scented Candle - Vanilla',          1,  189.00);

-- Order 1049 was returned and already refunded: the "already refunded, escalate" case.
INSERT INTO refunds (order_id, amount, reason, created_at) VALUES
(1049, 1899.00, 'Size too small, returned within window', '2026-09-26 11:02:00');
