from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session
import json
import os
import json
from werkzeug.utils import secure_filename
from datetime import datetime
import pytz
from collections import defaultdict

import google.generativeai as genai

# Configure Gemini API
API_KEY = "AIzaSyC3aNlBGGmJqasAgBDEWXNe4aZgj4KyDCA"
def configure_api_key(api_key):
    if not api_key:
        raise ValueError("Please provide your Gemini API key. Do not embed it in code!")
    genai.configure(api_key=api_key)

try:
    configure_api_key(API_KEY)
except ValueError as e:
    print(f"Error: {e}")
    exit(1)


app = Flask(__name__)
app.secret_key = "your_secret_key"  # Required for session management
PRODUCTS_FILE = 'data/Products.txt'
IMAGE_FOLDER = 'product_images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure the image folder exists
os.makedirs(IMAGE_FOLDER, exist_ok=True)

app.config['IMAGE_FOLDER'] = IMAGE_FOLDER

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
INVOICE_FOLDER = "invoices"

# Ensure the invoices folder exists
if not os.path.exists(INVOICE_FOLDER):
    os.makedirs(INVOICE_FOLDER)

# Route to fetch the list of invoices
@app.route('/get_invoices')
def get_invoices():
    try:
        invoices = [f for f in os.listdir(INVOICE_FOLDER) if f.endswith(".pdf")]
        return jsonify({"invoices": invoices})
    except Exception as e:
        print(f"Error fetching invoices: {e}")
        return jsonify({"invoices": []})

# Route to handle the PDF upload
@app.route('/upload_invoice', methods=['POST'])
def upload_invoice():
    try:
        # Ensure the file is present in the request
        if 'pdf' not in request.files:
            return jsonify({"success": False, "message": "No file part"}), 400
        
        file = request.files['pdf']
        
        # Check if the file is a PDF
        if file.filename == '':
            return jsonify({"success": False, "message": "No selected file"}), 400
        
        if file and file.filename.endswith('.pdf'):
            # Save the file in the invoices folder
            file_path = os.path.join(INVOICE_FOLDER, file.filename)
            file.save(file_path)
            return jsonify({"success": True, "message": "File uploaded successfully"}), 200
        else:
            return jsonify({"success": False, "message": "Invalid file type, only PDF allowed"}), 400
    except Exception as e:
        print(f"Error uploading file: {e}")
        return jsonify({"success": False, "message": "An error occurred during upload"}), 500

# Route to serve the PDF files
@app.route('/invoices/<filename>')
def serve_invoice(filename):
    return send_from_directory(INVOICE_FOLDER, filename)

@app.route('/download_invoice/<invoice_name>')
def download_invoice(invoice_name):
    try:
        # Safely send the file from the invoices directory
        return send_from_directory(INVOICE_FOLDER, invoice_name, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"error": "Invoice not found"}), 404
    
@app.route('/delete_invoice/<invoice_name>', methods=['DELETE'])
def delete_invoice(invoice_name):
    try:
        invoice_path = os.path.join(INVOICE_FOLDER, invoice_name)
        if os.path.exists(invoice_path):
            os.remove(invoice_path)  # Delete the file
            return jsonify({"success": True, "message": "Invoice deleted successfully"}), 200
        else:
            return jsonify({"success": False, "message": "Invoice not found"}), 404
    except Exception as e:
        print(f"Error deleting invoice: {e}")
        return jsonify({"success": False, "message": "An error occurred while deleting the invoice"}), 500


ORDERS_FILE = "Orders.txt"

def get_top_clients():
    """Read Orders.txt and return a dictionary of total orders per client."""
    client_orders = defaultdict(int)

    with open(ORDERS_FILE, "r") as file:
        for line in file:
            parts = line.strip().split(" | ")
            if len(parts) < 2:
                continue
            
            details = parts[1].split(",")
            if len(details) < 2:
                continue
            
            client = details[0]  # Client name
            quantity = int(details[1])  # Order quantity
            
            client_orders[client] += quantity  # Aggregate orders

    sorted_clients = sorted(client_orders.items(), key=lambda x: x[1], reverse=True)
    return [{"client": client, "orders": orders} for client, orders in sorted_clients]

@app.route("/get_orders_data")
def get_orders_data():
    """API endpoint to return order data as JSON (optional if using fetch)."""
    return jsonify(get_top_clients())



def load_products():
    """Load products from PRODUCTS_FILE, return as a dictionary, removing empty categories."""
    if os.path.exists(PRODUCTS_FILE):
        # Check if the file is empty
        if os.path.getsize(PRODUCTS_FILE) == 0:
            return {}  # Return an empty dictionary if the file is empty
        try:
            with open(PRODUCTS_FILE, 'r') as f:
                products = json.load(f)  # Attempt to load the JSON data
            
            # Remove empty categories (categories with empty lists)
            products = {category: items for category, items in products.items() if items}

            return products
        except json.JSONDecodeError:
            # Handle JSON decoding errors (e.g., if the file is corrupted)
            print("Error: JSON file is corrupted. Returning an empty product list.")
            return {}
    return {}


def save_products(products):
    """Save products dictionary to PRODUCTS_FILE."""
    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(products, f, indent=4)

@app.route('/edit', methods=['POST'])
def edit_product():
    products = load_products()
    product_id = int(request.form['id'])
    updated_name = request.form['name']
    updated_category = request.form['category']
    updated_cost_price = request.form['cost_price']
    updated_selling_price = request.form['selling_price']
    updated_quantity = request.form['quantity']
    updated_supplier = request.form['supplier']
    updated_expiry = request.form['expiry']

    # Locate and update the product
    for category, items in products.items():
        for product in items:
            if product[0] == product_id:  # Accessing the ID at index 0
                # Update the product details based on their position in the list
                product[1] = updated_name
                product[2] = updated_category
                product[3] = updated_cost_price
                product[4] = updated_selling_price
                product[5] = updated_quantity
                product[7] = updated_supplier
                product[8] = updated_expiry
                break

    # Save updated products back to the file
    save_products(products)
    return redirect(url_for('index'))

@app.route('/delete', methods=['POST'])
def delete_product():
    products = load_products()
    data = request.get_json()
    product_id = int(data['id'])

    # Locate and delete the product
    for category, items in products.items():
        for product in items:
            if product[0] == product_id:  # Accessing the ID at index 0
                items.remove(product)
                break

    # Save the updated products back to the file
    save_products(products)
    return jsonify({"success": True}), 200

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded images."""
    return send_from_directory(app.config['IMAGE_FOLDER'], filename)

def get_product_counts():
    """Calculate total products and number of products in each category."""
    products = load_products()  # Load current products from file
    
    total_products = 0  # To hold the total number of products
    category_counts = {}  # To hold the count of products in each category
    
    # Iterate over all categories and count products
    for category, items in products.items():
        category_counts[category] = len(items)  # Count products in this category
        total_products += len(items)  # Add this category's products to the total

    return total_products, category_counts


@app.route('/', methods=['GET', 'POST'])
def index():
    products = load_products()
    username = session.get("username")  # Retrieve the username from the session

    # Determine whether to show the login popup
    show_login_popup = username is None
    
    # Get total products and category counts
    total_products, category_counts = get_product_counts()

    for category, items in products.items():
        products[category] = sorted(items, key=lambda x: (int(x[5]) == 0, int(x[5])))


    if request.method == 'POST':
        # Get form data
        name = request.form['name']
        category = request.form['category']
        cost_price = request.form['cost_price']
        selling_price = request.form['selling_price']
        quantity = request.form['quantity']
        supplier = request.form['supplier']
        expiry = request.form['expiry']

        # Auto-generate an ID based on total number of items
        product_id = sum(len(items) for items in products.values()) + 1

        # Handle file upload
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            image_path = os.path.join(app.config['IMAGE_FOLDER'], filename)
            file.save(image_path)
        else:
            filename = None  # No image uploaded

        # Create product entry
        product = [product_id, name, category, cost_price, selling_price, quantity, filename, supplier, expiry]

        # Add product to the appropriate category in the dictionary
        if category not in products:
            products[category] = []
        products[category].append(product)

        # Save updated products to file
        save_products(products)

        return redirect(url_for('index'))
    top_clients = get_top_clients()

    return render_template('index.html', top_clients=top_clients, products=products, total_products=total_products, category_counts=category_counts, username=username, show_login_popup=show_login_popup)

@app.route('/client')
def client():
    products = load_products()
    username = session.get("username")  # Retrieve the username from the session

    # Determine whether to show the login popup
    show_login_popup = username is None

    # Load order history
    if os.path.exists("data/Orders.txt"):
        with open("data/Orders.txt", "r") as f:
            orders = [line.strip().split(",") for line in f]
    else:
        orders = []

    # Filter orders for the logged-in user
    user_orders = [order for order in orders if order[0][22::] == username] if username else []

    for category, items in products.items():
        products[category] = sorted(items, key=lambda x: (int(x[5]) == 0, int(x[5])))

    return render_template(
        "client.html",
        products=products,
        user_orders=user_orders,
        username=username,
        show_login_popup=show_login_popup
    )

@app.route('/chat1', methods=['POST'])
def chat1():
    data = request.get_json()
    user_message = data.get('message')

    products = load_products()
    out_of_stock = []

    for category, items in products.items():
        for product in items:
            if int(product[5]) == 0:  # Check if quantity is 0
                   out_of_stock.append({
                    "id": product[0],
                       "name": product[1],
                       "category": product[2]
                   })
    avail_stock = []

    for category, items in products.items():
        for product in items:
            avail_stock.append({
                "name": product[1],
                "category": product[2]
            })

    order_hist = []
    with open('data/Orders.txt', 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 6:
                    order_hist.append({
                        'Time&ClientName': parts[-6],
                        'ProductId': parts[-5],
                        'OrderQuantity': parts[-4],
                        'OrderedProduct': parts[-3],
                        'Category': parts[-2]
                    })

    order_hist1 = []
    with open('data/Orders.txt', 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 6:
                    order_hist.append({
                        'Time&OrdererName': parts[-6],
                        'OrderQuantity': parts[-4],
                        'OrderedProduct': parts[-3],
                        'Category': parts[-2]
                    })
    if not user_message:
        return jsonify({'reply': 'Error: No message provided.'}), 400

    try:
        # Generate response using the Gemini API
        model = genai.GenerativeModel('gemini-1.0-pro')
        user_message = "Imagine yourself as a admin assistant who is ready to help the admin with the users or client or shop who come to your store. \nYour store is actually a warehouse that provides different products in different quantity. The clients are not charged with money, since the clients actually work for your warehouse sub brand companies. YOur job is to help them with the admin queries related to the stocks you have, only with the information related to the stocks. \nIf something or a product is asked, he should be said with a message indicating as 'what you are asking is out of the context, or I am unable to understand what you are asking'. Here below is the stock details : \n" + str(avail_stock) + "The out of stock products are:\n" + str(out_of_stock) + "THe products or stock or shop ordered by clients are as follows (Order HIstory):" + str(order_hist) + "Following is the name of the client or shop or user, with their respective time of ordering, and the product with its quantity detail, which will be helpful to resolve the questions related to the most and least orderer product with the user or shop or client name details etc:" + str(order_hist1) + "Now the client or shop or user message is as follows: "+ user_message +"\n Make sure the response you give now is as you are responding to the clients message."
        response = model.generate_content(user_message)
        bot_reply = response.text
    except Exception as e:
        bot_reply = f"Error: Unable to process your message. {str(e)}"

    return jsonify({'reply': bot_reply})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message')

    products = load_products()
    out_of_stock = []

    for category, items in products.items():
        for product in items:
            if int(product[5]) == 0:  # Check if quantity is 0
                   out_of_stock.append({
                    "id": product[0],
                       "name": product[1],
                       "category": product[2]
                   })
    avail_stock = []

    for category, items in products.items():
        for product in items:
            avail_stock.append({
                "name": product[1],
                "category": product[2]
            })

    order_hist = []
    with open('data/Orders.txt', 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 6:
                    order_hist.append({
                        'Time&ClientName': parts[-6],
                        'ProductId': parts[-5],
                        'OrderQuantity': parts[-4],
                        'OrderedProduct': parts[-3],
                        'Category': parts[-2]
                    })

    order_hist1 = []
    with open('data/Orders.txt', 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 6:
                    order_hist.append({
                        'Time&OrdererName': parts[-6],
                        'OrderQuantity': parts[-4],
                        'OrderedProduct': parts[-3],
                        'Category': parts[-2]
                    })
    if not user_message:
        return jsonify({'reply': 'Error: No message provided.'}), 400

    try:
        # Generate response using the Gemini API
        model = genai.GenerativeModel('gemini-1.0-pro')
        user_message = "Imagine yourself as a helpdesk employee who is ready to help users or client or shop who come to your store. \nYour store is actually a warehouse that provides different products in different quantity. These clients are not charged with money, since these clients actually work for your warehouse sub brand companies. YOur job is to help them with their queries related to the stocks you have, only with the information related to the stocks. \nIf something or a product is asked, he should be said with a message indicating as 'what you are asking is out of the context, or I am unable to understand what you are asking'. Here below is the stock details : \n" + str(avail_stock) + "The out of stock products are:\n" + str(out_of_stock) + "THe products or stock or shop ordered by clients are as follows (Order HIstory):" + str(order_hist) + "Following is the name of the client or shop or user, with their respective time of ordering, and the product with its quantity detail, which will be helpful to resolve the questions related to the most and least orderer product with the user or shop or client name details etc:" + str(order_hist1) + "Now the client or shop or user message is as follows: "+ user_message +"\n Make sure the response you give now is as you are responding to the clients message."
        response = model.generate_content(user_message)
        bot_reply = response.text
    except Exception as e:
        bot_reply = f"Error: Unable to process your message. {str(e)}"

    return jsonify({'reply': bot_reply})
    

@app.route('/get-notify-messages', methods=['GET'])
def get_notify_messages():
    try:
        if os.path.exists("data/notify.txt"):
            with open("data/notify.txt", "r") as f:
                messages = f.readlines()
        else:
            messages = []

        return jsonify({"messages": [msg.strip() for msg in messages]})
    except Exception as e:
        print(f"Error reading notify.txt: {e}")
        return jsonify({"messages": []}), 500
    
ORDERS_FILE = "data/Orders.txt"

def parse_orders():
    """Parse the Orders.txt file to aggregate order data."""
    categories = defaultdict(int)  # Aggregate quantities by category
    products = defaultdict(lambda: defaultdict(int))  # Aggregate products within categories

    try:
        with open(ORDERS_FILE, "r") as file:
            for line in file:
                parts = line.strip().split("|")
                if len(parts) < 2:  # Ensure enough components exist
                    continue
                
                # Fix: Parse from parts[1], not parts[-1]
                details = parts[1].split(",")
                if len(details) < 5:  # Ensure it has enough components
                    continue
                
                # Correct extraction
                quantity = int(details[2].strip())  # Second item is the quantity
                product = details[3].strip()       # Fourth item is the product
                category = details[4].strip()      # Fifth item is the category

                # Update totals
                categories[category] += quantity
                products[category][product] += quantity

        return {
            "categories": dict(categories),  # Convert defaultdict to regular dict
            "products": {cat: dict(items) for cat, items in products.items()}
        }
    except Exception as e:
        print(f"Error reading orders: {e}")
        return {"categories": {}, "products": {}}
        

@app.route('/clearorders', methods=['POST'])
def clear_orders():
    try:
        # Open the orders.txt file and clear its contents
        with open('data/Orders.txt', 'w') as file:
            file.truncate(0)  # Clears the file
        return jsonify({"success": True})
    except Exception as e:
        print("Error clearing orders:", e)
        return jsonify({"success": False})
    
@app.route('/clearnotify', methods=['POST'])
def clear_notify():
    try:
        # Open the orders.txt file and clear its contents
        with open('data/notify.txt', 'w') as file:
            file.truncate(0)  # Clears the file
        return jsonify({"success": True})
    except Exception as e:
        print("Error clearing notify:", e)
        return jsonify({"success": False})
    
@app.route('/get-report-data')
def get_report_data():
    order_data = parse_orders()
    return jsonify(order_data)

from collections import Counter

@app.route('/get_chart_data')
def get_chart_data():
    PRODUCTS_FILE = "data/Products.txt"
    supplier_counts = Counter()

    try:
        with open(PRODUCTS_FILE, "r") as f:
            products = json.load(f)

        for category, items in products.items():
            for item in items:
                supplier = item[7]  # Adjust the index based on your data structure
                supplier_counts[supplier] += 1

        return jsonify({"supplierData": dict(supplier_counts)})
    except Exception as e:
        print(f"Error fetching supplier data: {e}")
        return jsonify({"supplierData": {}})


@app.route('/get-orders', methods=['GET'])
def get_orders():
    orders = []
    try:
        with open('data/Orders.txt', 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 6:
                    orders.append({
                        'filtername': parts[0][22::],
                        'username': parts[0],
                        'productId': parts[1],
                        'quantity': parts[2],
                        'productName': parts[3],
                        'category': parts[4],
                        'message': parts[5]
                    })
    except FileNotFoundError:
        pass  # Return an empty list if the file doesn't exist

    return jsonify(orders)

@app.route('/get-out-of-stock-products', methods=['GET'])
def get_out_of_stock_products():
    try:
        products = load_products()
        out_of_stock = []

        for category, items in products.items():
            for product in items:
                if int(product[5]) == 0:  # Check if quantity is 0
                    out_of_stock.append({
                        "id": product[0],
                        "name": product[1],
                        "category": product[2]
                    })

        return jsonify({"products": out_of_stock})
    except Exception as e:
        print(f"Error loading products: {e}")
        return jsonify({"products": []}), 500



# Load credentials from the file
with open('data/cred.txt', 'r') as f:
    credentials = json.load(f)


@app.route("/validate-login", methods=["POST"])
def validate_login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if username in credentials and credentials[username] == password:
        session["username"] = username  # Store username in the session
        return jsonify({"message": "Login successful"}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

@app.route('/logout')
def logout():
    # Clear the session (logging the user out)
    session.pop("username", None)  # Removes 'username' from the session
    return redirect(url_for('client'))
@app.route('/logoutindex')
def logoutindex():
    # Clear the session (logging the user out)
    session.pop("username", None)  # Removes 'username' from the session
    return redirect(url_for('index'))

@app.route('/notify', methods=['POST'])
def notify():
    data = request.get_json()
    product_id = data.get("product_id")
    product_name = data.get("product_name")
    product_category = data.get("product_category")
    username = session.get("username", "Guest")

    # Get the current time in Ireland timezone
    ireland_tz = pytz.timezone('Europe/Dublin')
    current_time = datetime.now(ireland_tz).strftime('%Y-%m-%d %H:%M:%S')

    # Save the notification details to notify.txt with timestamp
    notification_message = f"{current_time} : {username} asked for more stocks of Product ID: {product_id}, Name: {product_name}, Category: {product_category}\n"
    with open("data/notify.txt", "a") as f:
        f.write(notification_message)

    return redirect(url_for('client'))


@app.route('/place-order', methods=['POST'])
def place_order():
    products = load_products()
    product_id = request.form.get('id')  # Safely retrieve ID
    order_quantity = request.form.get('order_quantity')  # Safely retrieve quantity
    order_message = request.form.get('order_Message')
    username = session.get("username", "Guest")

    if not product_id or not order_quantity:
        return render_template(
            "client.html",
            products=products,
            message="Invalid product or quantity.",
            message_type="error",
            username=username
        )

    product_id = int(product_id)
    order_quantity = int(order_quantity)

    if not username or username == "Guest":
        return render_template(
            "client.html",
            products=products,
            show_login_popup=True,
            message="You need to log in to place an order.",
            message_type="error",
            username=username
        )

    # Load order history
    if os.path.exists("data/Orders.txt"):
        with open("data/Orders.txt", "r") as f:
            orders = [line.strip().split(",") for line in f]
    else:
        orders = []

    user_orders = [order for order in orders if order[0] == username]

    # Locate the product by ID
    for category, items in products.items():
        for product in items:
            if product[0] == product_id:
                available_quantity = int(product[5])  # Quantity is at index 5
                if order_quantity > available_quantity:
                    return render_template(
                        "client.html",
                        products=products,
                        message="Insufficient stock for the selected product.",
                        message_type="error",
                        user_orders=user_orders,
                        username=username
                    )

                # Update product quantity
                product[5] = str(available_quantity - order_quantity)

                # Save updated products
                save_products(products)
                ireland_tz = pytz.timezone('Europe/Dublin')
                current_time = datetime.now(ireland_tz).strftime('%Y-%m-%d %H:%M:%S')
                username = current_time + " | " + username
                # Log the order in a separate file
                with open("data/Orders.txt", "a") as order_file:
                    order_file.write(f"{username},{product_id},{order_quantity},{product[1]},{product[2]},{order_message}\n")

                # Reload order history
                user_orders.append([username, str(product_id), str(order_quantity), product[1], product[2], str(order_message)])

                return render_template(
                    "client.html",
                    products=products,
                    show_login_popup=False, 
                    message="Order placed successfully!",
                    message_type="success",
                    user_orders=user_orders,
                    username=username
                )

    return render_template(
        "client.html",
        products=products,
        show_login_popup=False, 
        message="Product not found.",
        message_type="error",
        user_orders=user_orders,
        username=username
    )



if __name__ == '__main__':
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(PRODUCTS_FILE), exist_ok=True)
    app.run(debug=True, host="0.0.0.0")