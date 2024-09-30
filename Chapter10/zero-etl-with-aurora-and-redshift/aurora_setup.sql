USE mydatabase;

CREATE TABLE products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    product_name VARCHAR(100),
    category VARCHAR(50),
    price DECIMAL(10,2)
);

CREATE TABLE sales (
    sale_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT,
    sale_amount DECIMAL(10,2),
    sale_date DATE,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

INSERT INTO products (product_name, category, price) VALUES
('Wireless Headphones', 'Electronics', 99.99),
('Running Shoes', 'Footwear', 79.99),
('Coffee Maker', 'Home Appliances', 49.99);

INSERT INTO sales (product_id, sale_amount, sale_date) VALUES
(1, 99.99, '2023-10-01'),
(2, 159.98, '2023-10-02'),
(3, 49.99, '2023-10-03');

-- Verify data
SELECT * FROM products;
SELECT * FROM sales;
