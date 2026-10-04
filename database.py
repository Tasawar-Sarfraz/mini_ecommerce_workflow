import sqlite3
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"
DATABASE_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATABASE_DIR / "inventory.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    connection = get_connection()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            price REAL NOT NULL CHECK(price >= 0),
            stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK(stock_quantity >= 0),
            low_stock_threshold INTEGER NOT NULL DEFAULT 3 CHECK(low_stock_threshold >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            total_amount REAL NOT NULL CHECK(total_amount >= 0),
            channel TEXT NOT NULL CHECK(
                channel IN ('WEBSITE', 'WHATSAPP', 'PHYSICAL_SHOP')
            ),
            status TEXT NOT NULL CHECK(
                status IN ('CONFIRMED', 'REJECTED')
            ),
            rejection_reason TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity_change INTEGER NOT NULL,
            stock_before INTEGER NOT NULL,
            stock_after INTEGER NOT NULL,
            transaction_type TEXT NOT NULL CHECK(
                transaction_type IN ('SALE', 'RESTOCK')
            ),
            channel TEXT,
            order_id INTEGER,
            reason TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );
        """
    )

    connection.commit()
    connection.close()


def get_products():
    connection = get_connection()

    products = connection.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()
    return products


def get_product(product_id: int):
    connection = get_connection()

    product = connection.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (product_id,),
    ).fetchone()

    connection.close()
    return product


def add_product(
    name: str,
    sku: str,
    category: str,
    price: float,
    stock_quantity: int,
    low_stock_threshold: int,
):
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO products
            (
                name,
                sku,
                category,
                price,
                stock_quantity,
                low_stock_threshold
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                sku,
                category,
                price,
                stock_quantity,
                low_stock_threshold,
            ),
        )

        connection.commit()
        return True, "Product added successfully."

    except sqlite3.IntegrityError as error:
        if "UNIQUE" in str(error):
            return False, "SKU already exists."

        return False, "Could not add product."

    finally:
        connection.close()


def create_order(
    customer_name: str,
    product_id: int,
    quantity: int,
    channel: str,
):
    if quantity <= 0:
        return False, "Quantity must be greater than zero."

    valid_channels = {
        "WEBSITE",
        "WHATSAPP",
        "PHYSICAL_SHOP",
    }

    if channel not in valid_channels:
        return False, "Invalid sales channel."

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        product = connection.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()

        if product is None:
            connection.rollback()
            return False, "Product not found."

        stock_before = product["stock_quantity"]

        if stock_before < quantity:
            connection.rollback()
            return False, (
                f"Insufficient stock. "
                f"Available: {stock_before}, Requested: {quantity}."
            )

        total_amount = product["price"] * quantity
        stock_after = stock_before - quantity

        cursor = connection.execute(
            """
            INSERT INTO orders
            (
                customer_name,
                product_id,
                quantity,
                total_amount,
                channel,
                status
            )
            VALUES (?, ?, ?, ?, ?, 'CONFIRMED')
            """,
            (
                customer_name,
                product_id,
                quantity,
                total_amount,
                channel,
            ),
        )

        order_id = cursor.lastrowid

        connection.execute(
            """
            UPDATE products
            SET stock_quantity = ?
            WHERE id = ?
            """,
            (
                stock_after,
                product_id,
            ),
        )

        connection.execute(
            """
            INSERT INTO inventory_transactions
            (
                product_id,
                quantity_change,
                stock_before,
                stock_after,
                transaction_type,
                channel,
                order_id,
                reason
            )
            VALUES (?, ?, ?, ?, 'SALE', ?, ?, ?)
            """,
            (
                product_id,
                -quantity,
                stock_before,
                stock_after,
                channel,
                order_id,
                "Customer order",
            ),
        )

        connection.commit()

        return True, (
            f"Order #{order_id} confirmed successfully. "
            f"Remaining stock: {stock_after}."
        )

    except sqlite3.Error:
        connection.rollback()
        return False, "Order could not be processed."

    finally:
        connection.close()


def restock_product(
    product_id: int,
    quantity: int,
    reason: str,
):
    if quantity <= 0:
        return False, "Restock quantity must be greater than zero."

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        product = connection.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()

        if product is None:
            connection.rollback()
            return False, "Product not found."

        stock_before = product["stock_quantity"]
        stock_after = stock_before + quantity

        connection.execute(
            """
            UPDATE products
            SET stock_quantity = ?
            WHERE id = ?
            """,
            (
                stock_after,
                product_id,
            ),
        )

        connection.execute(
            """
            INSERT INTO inventory_transactions
            (
                product_id,
                quantity_change,
                stock_before,
                stock_after,
                transaction_type,
                channel,
                order_id,
                reason
            )
            VALUES (?, ?, ?, ?, 'RESTOCK', NULL, NULL, ?)
            """,
            (
                product_id,
                quantity,
                stock_before,
                stock_after,
                reason.strip() or "Manual restock",
            ),
        )

        connection.commit()

        return True, (
            f"Stock updated successfully. "
            f"New stock: {stock_after}."
        )

    except sqlite3.Error:
        connection.rollback()
        return False, "Stock could not be updated."

    finally:
        connection.close()


def get_orders():
    connection = get_connection()

    orders = connection.execute(
        """
        SELECT
            orders.id,
            orders.customer_name,
            products.name AS product_name,
            products.sku,
            orders.quantity,
            orders.total_amount,
            orders.channel,
            orders.status,
            orders.rejection_reason,
            orders.created_at
        FROM orders
        INNER JOIN products
            ON orders.product_id = products.id
        ORDER BY orders.id DESC
        """
    ).fetchall()

    connection.close()
    return orders


def get_inventory_transactions():
    connection = get_connection()

    transactions = connection.execute(
        """
        SELECT
            inventory_transactions.id,
            products.name AS product_name,
            products.sku,
            inventory_transactions.quantity_change,
            inventory_transactions.stock_before,
            inventory_transactions.stock_after,
            inventory_transactions.transaction_type,
            inventory_transactions.channel,
            inventory_transactions.order_id,
            inventory_transactions.reason,
            inventory_transactions.created_at
        FROM inventory_transactions
        INNER JOIN products
            ON inventory_transactions.product_id = products.id
        ORDER BY inventory_transactions.id DESC
        """
    ).fetchall()

    connection.close()
    return transactions


def get_dashboard_stats():
    connection = get_connection()

    stats = connection.execute(
        """
        SELECT
            COUNT(*) AS total_products,
            COALESCE(SUM(stock_quantity), 0) AS total_stock,
            COALESCE(
                SUM(
                    CASE
                        WHEN stock_quantity = 0 THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS out_of_stock,
            COALESCE(
                SUM(
                    CASE
                        WHEN stock_quantity > 0
                         AND stock_quantity <= low_stock_threshold
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS low_stock
        FROM products
        """
    ).fetchone()

    connection.close()
    return stats
