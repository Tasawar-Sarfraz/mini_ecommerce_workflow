import streamlit as st
import pandas as pd

from database import (
    initialize_database,
    get_products,
    add_product,
    create_order,
    restock_product,
    get_orders,
    get_inventory_transactions,
    get_dashboard_stats,
)


st.set_page_config(
    page_title="Inventory Sync Store",
    page_icon="🛒",
    layout="wide",
)


initialize_database()


def products_to_dataframe(products):
    if not products:
        return pd.DataFrame()

    data = [dict(product) for product in products]

    dataframe = pd.DataFrame(data)

    dataframe = dataframe[
        [
            "id",
            "name",
            "sku",
            "category",
            "price",
            "stock_quantity",
            "low_stock_threshold",
            "created_at",
        ]
    ]

    dataframe.columns = [
        "ID",
        "Product",
        "SKU",
        "Category",
        "Price",
        "Stock",
        "Low Stock Threshold",
        "Created At",
    ]

    return dataframe


def orders_to_dataframe(orders):
    if not orders:
        return pd.DataFrame()

    data = [dict(order) for order in orders]

    dataframe = pd.DataFrame(data)

    dataframe = dataframe[
        [
            "id",
            "customer_name",
            "product_name",
            "sku",
            "quantity",
            "total_amount",
            "channel",
            "status",
            "rejection_reason",
            "created_at",
        ]
    ]

    dataframe.columns = [
        "Order ID",
        "Customer",
        "Product",
        "SKU",
        "Quantity",
        "Total",
        "Channel",
        "Status",
        "Reason",
        "Created At",
    ]

    return dataframe


def transactions_to_dataframe(transactions):
    if not transactions:
        return pd.DataFrame()

    data = [dict(transaction) for transaction in transactions]

    dataframe = pd.DataFrame(data)

    dataframe = dataframe[
        [
            "id",
            "product_name",
            "sku",
            "quantity_change",
            "stock_before",
            "stock_after",
            "transaction_type",
            "channel",
            "order_id",
            "reason",
            "created_at",
        ]
    ]

    dataframe.columns = [
        "Transaction ID",
        "Product",
        "SKU",
        "Quantity Change",
        "Stock Before",
        "Stock After",
        "Type",
        "Channel",
        "Order ID",
        "Reason",
        "Created At",
    ]

    return dataframe


st.title("🛒 Inventory Sync E-commerce")
st.caption(
    "Central inventory system for Website, WhatsApp and Physical Shop"
)


dashboard = st.sidebar.radio(
    "Select Dashboard",
    [
        "Customer Dashboard",
        "Admin / Inventory Dashboard",
    ],
)


# ============================================================
# CUSTOMER DASHBOARD
# ============================================================

if dashboard == "Customer Dashboard":

    st.header("🛍️ Customer Dashboard")

    products = get_products()

    if not products:
        st.info("No products are available yet.")
    else:

        st.subheader("Available Products")

        for product in products:

            col1, col2, col3, col4 = st.columns(
                [3, 2, 2, 2]
            )

            with col1:
                st.write(f"**{product['name']}**")
                st.caption(
                    f"SKU: {product['sku']} | "
                    f"Category: {product['category']}"
                )

            with col2:
                st.write(
                    f"**Rs. {product['price']:,.2f}**"
                )

            with col3:
                stock = product["stock_quantity"]

                if stock == 0:
                    st.error("Out of Stock")
                elif stock <= product["low_stock_threshold"]:
                    st.warning(
                        f"Low Stock: {stock}"
                    )
                else:
                    st.success(
                        f"In Stock: {stock}"
                    )

            with col4:
                st.write("")

        st.divider()

        st.subheader("Place Order")

        product_options = {
            f"{product['name']} | "
            f"SKU: {product['sku']} | "
            f"Stock: {product['stock_quantity']}": product["id"]
            for product in products
        }

        selected_product_label = st.selectbox(
            "Select Product",
            list(product_options.keys()),
        )

        selected_product_id = product_options[
            selected_product_label
        ]

        selected_product = next(
            product
            for product in products
            if product["id"] == selected_product_id
        )

        customer_name = st.text_input(
            "Customer Name"
        )

        quantity = st.number_input(
            "Quantity",
            min_value=1,
            value=1,
            step=1,
        )

        channel = st.selectbox(
            "Order Channel",
            [
                "WEBSITE",
                "WHATSAPP",
                "PHYSICAL_SHOP",
            ],
        )

        estimated_total = (
            selected_product["price"] * quantity
        )

        st.write(
            f"**Order Total: Rs. "
            f"{estimated_total:,.2f}**"
        )

        if st.button(
            "Place Order",
            type="primary",
            use_container_width=True,
        ):

            if not customer_name.strip():
                st.error(
                    "Please enter customer name."
                )

            else:
                success, message = create_order(
                    customer_name=customer_name.strip(),
                    product_id=selected_product_id,
                    quantity=int(quantity),
                    channel=channel,
                )

                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


# ============================================================
# ADMIN / INVENTORY DASHBOARD
# ============================================================

else:

    st.header("📊 Admin / Inventory Dashboard")

    stats = get_dashboard_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Products",
            stats["total_products"],
        )

    with col2:
        st.metric(
            "Total Stock",
            stats["total_stock"],
        )

    with col3:
        st.metric(
            "Low Stock",
            stats["low_stock"],
        )

    with col4:
        st.metric(
            "Out of Stock",
            stats["out_of_stock"],
        )

    st.divider()

    # --------------------------------------------------------
    # INVENTORY
    # --------------------------------------------------------

    st.subheader("📦 Current Inventory")

    products = get_products()

    products_dataframe = products_to_dataframe(
        products
    )

    if products_dataframe.empty:
        st.info("No products found.")
    else:
        st.dataframe(
            products_dataframe,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # --------------------------------------------------------
    # ADD PRODUCT
    # --------------------------------------------------------

    st.subheader("➕ Add Product")

    with st.form("add_product_form"):

        col1, col2 = st.columns(2)

        with col1:
            product_name = st.text_input(
                "Product Name"
            )

            sku = st.text_input(
                "SKU"
            )

            category = st.text_input(
                "Category"
            )

        with col2:
            price = st.number_input(
                "Price",
                min_value=0.0,
                step=100.0,
            )

            stock_quantity = st.number_input(
                "Initial Stock",
                min_value=0,
                step=1,
            )

            low_stock_threshold = st.number_input(
                "Low Stock Threshold",
                min_value=0,
                value=3,
                step=1,
            )

        add_product_button = st.form_submit_button(
            "Add Product",
            type="primary",
            use_container_width=True,
        )

    if add_product_button:

        if not product_name.strip():
            st.error("Product name is required.")

        elif not sku.strip():
            st.error("SKU is required.")

        elif not category.strip():
            st.error("Category is required.")

        else:

            success, message = add_product(
                name=product_name.strip(),
                sku=sku.strip().upper(),
                category=category.strip(),
                price=float(price),
                stock_quantity=int(stock_quantity),
                low_stock_threshold=int(
                    low_stock_threshold
                ),
            )

            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    st.divider()

    # --------------------------------------------------------
    # RESTOCK
    # --------------------------------------------------------

    st.subheader("🔄 Restock Inventory")

    products = get_products()

    if products:

        restock_options = {
            f"{product['name']} | "
            f"SKU: {product['sku']} | "
            f"Current Stock: {product['stock_quantity']}": product[
                "id"
            ]
            for product in products
        }

        selected_restock_label = st.selectbox(
            "Select Product for Restock",
            list(restock_options.keys()),
        )

        selected_restock_product_id = restock_options[
            selected_restock_label
        ]

        restock_quantity = st.number_input(
            "Restock Quantity",
            min_value=1,
            value=1,
            step=1,
        )

        restock_reason = st.text_input(
            "Restock Reason",
            value="Supplier stock received",
        )

        if st.button(
            "Update Stock",
            type="primary",
            use_container_width=True,
        ):

            success, message = restock_product(
                product_id=selected_restock_product_id,
                quantity=int(restock_quantity),
                reason=restock_reason,
            )

            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    else:
        st.info("Add a product before restocking.")

    st.divider()

    # --------------------------------------------------------
    # ORDERS
    # --------------------------------------------------------

    st.subheader("🧾 Orders")

    orders = get_orders()

    orders_dataframe = orders_to_dataframe(
        orders
    )

    if orders_dataframe.empty:
        st.info("No orders found.")
    else:
        st.dataframe(
            orders_dataframe,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # --------------------------------------------------------
    # INVENTORY TRANSACTIONS
    # --------------------------------------------------------

    st.subheader("📜 Inventory Transaction History")

    transactions = get_inventory_transactions()

    transactions_dataframe = transactions_to_dataframe(
        transactions
    )

    if transactions_dataframe.empty:
        st.info(
            "No inventory transactions found."
        )
    else:
        st.dataframe(
            transactions_dataframe,
            use_container_width=True,
            hide_index=True,
        )
