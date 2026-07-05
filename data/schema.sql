-- =====================================================================
--  "Shop" sample database for the SQL Learning IDE
--  Written in a portable, MySQL-flavoured style. Runs on the built-in
--  SQLite engine as-is, and maps cleanly onto a real MySQL server.
-- =====================================================================

CREATE TABLE customers (
  id          INTEGER      PRIMARY KEY,
  name        VARCHAR(80)  NOT NULL,
  city        VARCHAR(60),
  country     VARCHAR(60),
  signup_date DATE
);

CREATE TABLE products (
  id       INTEGER       PRIMARY KEY,
  name     VARCHAR(120)  NOT NULL,
  category VARCHAR(60),
  price    DECIMAL(10,2) NOT NULL,
  stock    INTEGER       NOT NULL
);

CREATE TABLE orders (
  id          INTEGER     PRIMARY KEY,
  customer_id INTEGER     NOT NULL,
  order_date  DATE,
  status      VARCHAR(20)
);

CREATE TABLE order_items (
  id         INTEGER       PRIMARY KEY,
  order_id   INTEGER       NOT NULL,
  product_id INTEGER       NOT NULL,
  quantity   INTEGER       NOT NULL,
  unit_price DECIMAL(10,2) NOT NULL
);

-- ---- customers -------------------------------------------------------
INSERT INTO customers (id, name, city, country, signup_date) VALUES
  (1, 'Aarav Sharma', 'Mumbai',   'India',       '2023-01-15'),
  (2, 'Bella Rossi',  'Rome',     'Italy',       '2023-03-22'),
  (3, 'Chen Wei',     'Shanghai', 'China',       '2023-02-10'),
  (4, 'Diego Lopez',  'Madrid',   'Spain',       '2023-05-05'),
  (5, 'Emma Johnson', 'London',   'UK',          '2023-04-18'),
  (6, 'Farah Khan',   'Mumbai',   'India',       '2023-06-30'),
  (7, 'Grace Lee',    'Seoul',    'South Korea', '2023-07-12'),
  (8, 'Hiro Tanaka',  'Tokyo',    'Japan',       '2023-08-01');

-- ---- products --------------------------------------------------------
INSERT INTO products (id, name, category, price, stock) VALUES
  (1,  'Wireless Mouse',              'Electronics', 25.00,  120),
  (2,  'Mechanical Keyboard',         'Electronics', 75.50,  60),
  (3,  'USB-C Cable',                 'Accessories', 9.99,   300),
  (4,  'Laptop Stand',                'Accessories', 34.00,  45),
  (5,  'Noise-Cancelling Headphones', 'Electronics', 199.00, 25),
  (6,  'Desk Lamp',                   'Home',        42.50,  80),
  (7,  'Notebook',                    'Stationery',  4.50,   500),
  (8,  'Gel Pen Pack',                'Stationery',  6.25,   400),
  (9,  'Monitor 27in',                'Electronics', 289.00, 15),
  (10, 'Webcam HD',                   'Electronics', 59.00,  0);

-- ---- orders ----------------------------------------------------------
INSERT INTO orders (id, customer_id, order_date, status) VALUES
  (1,  1, '2023-09-01', 'completed'),
  (2,  2, '2023-09-03', 'shipped'),
  (3,  1, '2023-09-10', 'completed'),
  (4,  3, '2023-09-12', 'pending'),
  (5,  5, '2023-09-15', 'completed'),
  (6,  6, '2023-09-20', 'cancelled'),
  (7,  7, '2023-10-01', 'shipped'),
  (8,  2, '2023-10-05', 'completed'),
  (9,  8, '2023-10-09', 'pending'),
  (10, 1, '2023-10-15', 'completed'),
  (11, 4, '2023-10-20', 'shipped'),
  (12, 5, '2023-11-02', 'completed');

-- ---- order_items -----------------------------------------------------
INSERT INTO order_items (id, order_id, product_id, quantity, unit_price) VALUES
  (1,  1,  1,  2,  25.00),
  (2,  1,  3,  3,  9.99),
  (3,  2,  5,  1,  199.00),
  (4,  3,  2,  1,  75.50),
  (5,  3,  4,  2,  34.00),
  (6,  4,  7,  10, 4.50),
  (7,  5,  9,  1,  289.00),
  (8,  5,  1,  1,  25.00),
  (9,  6,  6,  2,  42.50),
  (10, 7,  5,  1,  199.00),
  (11, 7,  3,  5,  9.99),
  (12, 8,  2,  2,  75.50),
  (13, 8,  8,  4,  6.25),
  (14, 9,  10, 1,  59.00),
  (15, 10, 9,  1,  289.00),
  (16, 10, 4,  1,  34.00),
  (17, 11, 1,  3,  25.00),
  (18, 12, 5,  2,  199.00),
  (19, 12, 6,  1,  42.50),
  (20, 3,  7,  5,  4.50);
