from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session
import json
import os
import json
from werkzeug.utils import secure_filename
from datetime import datetime
import pytz
from collections import defaultdict
import re
import google.generativeai as genai
from datetime import timedelta

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

    with open("data/OrderHistory.txt", "r") as file:
        for line in file:
            parts = line.strip().split(" | ")
            if len(parts) < 2:
                continue
            
            details = parts[1].split(",")
            if len(details) < 2:
                continue
            
            client = details[0]  # Client name
            try:
                quantity = int(details[2])  # Order quantity
            except:
                quantity = float(details[2])  # Order quantity
            
            client_orders[client] += quantity  # Aggregate orders

    sorted_clients = sorted(client_orders.items(), key=lambda x: x[1], reverse=True)
    return [{"client": client, "orders": orders} for client, orders in sorted_clients]

@app.route("/get_orders_data")
def get_orders_data():
    """API endpoint to return order data as JSON (optional if using fetch)."""
    return jsonify(get_top_clients())


CATEGORIES_PER_PAGE = 5  # Show 5 categories per page


@app.route('/get_products/<category>')
def get_products1(category):
    products = load_products()  # Load all products
    category_products = products.get(category, [])  # Get products for the selected category
    return jsonify(category_products)  # Return as JSON

@app.route('/get_categories')
def get_categories():
    products = load_products()
    categories = list(products.keys())  # Get all category names
    return jsonify({"categories": categories})



# ✅ Function to read product categories from file safely
def get_product_categories():
    try:
        with open("data/Products.txt", "r", encoding="utf-8") as file:
            products = json.load(file)  # ✅ Use json.load() instead of eval()
            return list(products.keys())  # ✅ Extract only category names
    except json.JSONDecodeError as e:
        print("Error reading product file (JSON issue):", e)
    except Exception as e:
        print("General error reading product file:", e)

    return []  # Return an empty list if there's an error

# ✅ API Endpoint to fetch matching categories
@app.route('/get_categories2')
def get_categories2():
    query = request.args.get("query", "").strip().lower()
    categories = get_product_categories()

    # ✅ Filter categories dynamically
    filtered_categories = [category for category in categories if category.lower().startswith(query)] if query else categories

    return jsonify(filtered_categories)

def load_products():
    """Load products from PRODUCTS_FILE, return as a dictionary, removing empty categories."""
    if os.path.exists(PRODUCTS_FILE):
        if os.path.getsize(PRODUCTS_FILE) == 0:
            print("⚠️ Warning: Products file is empty. Returning an empty list.")
            return {}  # File is empty, return empty dictionary

        try:
            with open(PRODUCTS_FILE, 'r') as f:
                data = f.read()
                products = json.loads(data)  # ✅ Load properly
            return {category: items for category, items in products.items() if items}  # Remove empty categories
        except json.JSONDecodeError as e:
            print(f"❌ Error: JSON file is corrupted! {e}")
            return {}
    print("⚠️ Warning: Products file does not exist.")
    return {}


def get_product_counts():
    """Ensure this function returns total product count and a dictionary of category counts."""
    products = load_products()
    total_products = sum(len(items) for items in products.values())  # Count total products
    category_counts = {category: len(items) for category, items in products.items()}
    return total_products, category_counts


def save_products(products):
    """Save products dictionary to PRODUCTS_FILE."""
    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(products, f, indent=4)

@app.route('/edit', methods=['POST'])
def edit_product():
    products = load_products()  # Load the current products
    product_id = int(request.form['id'])  # Get the product ID

    # Updated product details
    updated_name = sanitize_input(request.form['name'].strip())
    updated_category = sanitize_input(request.form['category'].strip())
    updated_cost_price = request.form['cost_price']
    updated_selling_price = request.form['selling_price']
    updated_quantity = request.form['quantity']
    updated_supplier = sanitize_input(request.form['supplier'].strip())
    updated_expiry = request.form['expiry'].strip()

    # Ensure expiry format is always DD-MM-YYYY
    updated_expiry = updated_expiry.replace("/", "-").replace(".", "-").replace("'", "").replace('"', '')
    updated_quantity = updated_quantity.replace(".00","").replace(".","")

    image = request.files.get('image')  # Get image file (if updated)
    existing_image = None  # Store the existing image filename

    # Step 1: Remove old product and store the existing image filename
    for category, items in products.items():
        for product in items:
            if product[0] == product_id:  # Match by ID
                existing_image = product[6]  # Get old image filename
                break
        products[category] = [product for product in items if product[0] != product_id]  # Remove old product

    # Step 2: Handle image update logic
    if image and image.filename:  
        filename = secure_filename(image.filename)  # Save new image
        image_path = os.path.join("product_images", filename)
        image.save(image_path)
    else:
        filename = existing_image  # Keep existing image if no new one is uploaded

    # Step 3: Create updated product list
    updated_product = [
        product_id, updated_name, updated_category, updated_cost_price,
        updated_selling_price, updated_quantity, filename, updated_supplier, updated_expiry
    ]

    # Step 4: Add updated product to the new category
    if updated_category not in products:
        products[updated_category] = []
    products[updated_category].append(updated_product)

    # Step 5: Save updated products back to file
    save_products(products)

    print(f"✅ Product {product_id} updated with image: {filename}")
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

def sanitize_input(input_string):
    """Sanitize the input by removing special characters."""
    return re.sub(r"[\'\":,]", "", input_string)


ID_FILE = "last_product_id.txt"

@app.route('/007PageLoginAdminThe007', methods=['GET', 'POST'])
def index():
    products = load_products()
    username = session.get("username")
    show_login_popup = username is None
    total_products, category_counts = get_product_counts()
    notepads = [f for f in os.listdir(MESSAGE_DIR) if f.endswith('.txt')]

    # Sort products within each category
    for category, items in products.items():
        try:
            products[category] = sorted(items, key=lambda x: (float(x[5]) == 0, float(x[5])))
        except ValueError as e:
            print(f"ValueError: {e} while sorting products in category {category}")

    # Handle Product Addition
    if request.method == 'POST':
        # Sanitize inputs to remove unwanted special characters
        name = sanitize_input(request.form['name'].strip()) if request.form['name'] else ''
        category = sanitize_input(request.form['category2'].strip()) if request.form['category2'] else ''
        supplier = sanitize_input(request.form['supplier'].strip()) if request.form['supplier'] else ''
        
        # Cost, Selling, and Quantity with default values if empty
        cost_price = request.form['cost_price'].strip() if request.form['cost_price'] else '0'
        selling_price = request.form['selling_price'].strip() if request.form['selling_price'] else '0'
        quantity = request.form['quantity'].strip() if request.form['quantity'] else '0'
        expiry = request.form['expiry'].strip() if request.form['expiry'] else ''
        
        quantity = quantity.replace(".00","").replace(".","")
        
        # ✅ Validate numeric fields
        try:
            cost_price = float(cost_price)
            selling_price = float(selling_price)
            try:
                quantity = int(quantity)
            except:
                quantity = float(quantity)
        except ValueError:
            print("❌ Error: Cost Price, Selling Price, or Quantity is invalid")
            return "Invalid numerical values", 400

        # ✅ Ensure expiry date format is consistent
        expiry = expiry.replace("/", "-").replace(".", "-").replace("'","").replace('"','')  # Replace slashes/dots with hyphens

        if expiry:
            expiry_parts = expiry.split("-")
            if len(expiry_parts) == 3:
                expiry = "-".join([expiry_parts[0].zfill(2), expiry_parts[1].zfill(2), expiry_parts[2]])
            else:
                print("⚠️ Warning: Invalid expiry format")
                expiry = ""

        # ✅ Ensure category exists in dictionary before adding the product
        if category not in products:
            products[category] = []

        if os.path.exists(ID_FILE):
            with open(ID_FILE, "r") as file:
                last_product_id = int(file.read().strip())
        else:
            last_product_id = 2000  # Default starting ID

        product_id = last_product_id + 1  # Increment product ID

        # ✅ Save updated product ID to file
        with open(ID_FILE, "w") as file:
            file.write(str(product_id))

        # ✅ Image handling
        file = request.files['image']
        filename = None  # Default
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            image_path = os.path.join(app.config['IMAGE_FOLDER'], filename)
            file.save(image_path)

        # ✅ Create the product list entry
        product = [product_id, name, category, cost_price, selling_price, quantity, filename, supplier, expiry]

        # ✅ Add product to the correct category
        products[category].append(product)

        # ✅ Try saving to file
        try:
            save_products(products)
            print("✅ Successfully saved products.")
        except Exception as e:
            print(f"❌ Error saving products: {e}")

        return redirect(url_for('index'))


    # **API for infinite scrolling**
    if request.args.get("load_more"):
        start = int(request.args.get("start", 0))
        limit = 5000  # Load 5 categories at a time

        all_categories = list(products.keys())
        next_categories = all_categories[start:start + limit]

        paginated_products = {category: products[category] for category in next_categories}

        return jsonify({"products": paginated_products, "has_more": len(next_categories) == limit})  # Indicate if more products exist

    return render_template(
        'index.html',
        top_clients=get_top_clients() or [],
        products={},  # Initially, load empty products (frontend will fetch them)
        total_products=total_products,
        category_counts=category_counts,
        username=username,
        show_login_popup=show_login_popup,
        notepads=notepads
    )

@app.route('/get-notepad', methods=['GET'])
def get_notepad():
    filename = request.args.get('filename')

    if not filename or not filename.endswith('.txt'):
        return jsonify({'success': False, 'message': 'Invalid file'})

    file_path = os.path.join(MESSAGE_DIR, filename)
    
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'message': 'File not found'})

    with open(file_path, 'r', encoding='utf-8', errors="replace") as file:
        content = file.read()

    return jsonify({'success': True, 'filename': filename, 'content': content})

@app.route('/save-notepad', methods=['POST'])
def save_notepad():
    data = request.json
    filename = data.get('filename')
    content = data.get('content')

    if not filename or not content:
        return jsonify({'success': False, 'message': 'Invalid data'})

    file_path = os.path.join(MESSAGE_DIR, filename)

    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)

    return jsonify({'success': True, 'message': 'Notepad saved successfully'})


@app.route('/client')
def client():
    products = load_products()
    categories = list(products.keys())
    username = session.get("username")
    show_login_popup = username is None

    # Load order history
    if os.path.exists("data/Orders.txt"):
        with open("data/Orders.txt", "r") as f:
            orders = [line.strip().split(",") for line in f]
    else:
        orders = []

    user_orders = [order for order in orders if order[0][22::] == username] if username else []

    # Sort products
    for category, items in products.items():
        try:
            products[category] = sorted(items, key=lambda x: (float(x[5]) == 0, float(x[5])))
        except ValueError as e:
            print(f"ValueError: {e} while sorting products in category {category}")

    # **API for initial load & infinite scroll**
    if request.args.get("load_more"):
        start = int(request.args.get("start", 0))
        limit = int(request.args.get("limit", 10))  # Load 5 categories initially

        all_categories = categories
        next_categories = all_categories[start:start + limit]

        paginated_products = {category: products[category] for category in next_categories}
        return jsonify({"products": paginated_products, "has_more": len(next_categories) == limit})


    return render_template(
        "client.html",
        user_orders=user_orders,
        username=username,
        show_login_popup=show_login_popup,
        categories=categories
    )


@app.route('/get_quantity')
def get_quantity():
    products = load_products()  # Function that loads Products.txt as a dictionary
    quantities = {}

    for category, items in products.items():
        for product in items:
            product_id = product[0]  # Unique ID
            quantity = product[5]  # Quantity value
            quantities[product_id] = quantity
    
    return jsonify(quantities)

@app.route('/chat1', methods=['POST'])
def chat1():
    data = request.get_json()
    user_message = data.get('message')

    products = load_products()
    out_of_stock = []

    for category, items in products.items():
        for product in items:
            try:
                if int(product[5]) == 0:  # Check if quantity is 0
                       out_of_stock.append({
                        "id": product[0],
                           "name": product[1],
                           "category": product[2]
                       })
            except:
                if float(product[5]) == 0:  # Check if quantity is 0
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
            try:
                if int(product[5]) == 0:  # Check if quantity is 0
                       out_of_stock.append({
                        "id": product[0],
                           "name": product[1],
                           "category": product[2]
                       })
            except:
                if float(product[5]) == 0:  # Check if quantity is 0
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
        with open("data/OrderHistory.txt", "r") as file:
            for line in file:
                parts = line.strip().split("|")
                if len(parts) < 2:  # Ensure enough components exist
                    continue
                
                # Fix: Parse from parts[1], not parts[-1]
                details = parts[1].split(",")
                if len(details) < 5:  # Ensure it has enough components
                    continue
                
                # Correct extraction
                try:
                    quantity = int(details[2].strip())  # Second item is the quantity
                except:
                    quantity = float(details[2].strip())  # Second item is the quantity
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
                        'date': parts[0][:10],
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

@app.route('/get-order-history', methods=['GET'])
def get_order_history():
    history_orders = []
    try:
        with open('data/OrderHistory.txt', 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 6:
                    history_orders.append({
                        'filtername': parts[0][22::],
                        'date': parts[0][:10],
                        'username': parts[0],
                        'productId': parts[1],
                        'quantity': parts[2],
                        'productName': parts[3],
                        'category': parts[4],
                        'message': parts[5]
                    })
    except FileNotFoundError:
        return jsonify([])  # Return an empty list if the file doesn't exist

    return jsonify(history_orders)

MESSAGE_DIR = "messages"
os.makedirs(MESSAGE_DIR, exist_ok=True)

@app.route('/get-message', methods=['GET'])
def get_message751():
    username = request.args.get('username', '')

    if not username:
        return jsonify({'success': False, 'message': 'Username is required'})

    file_path = os.path.join(MESSAGE_DIR, f"{username}.txt")

    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            message = file.read()
    else:
        message = ""

    return jsonify({'success': True, 'message': message})


@app.route('/save-message', methods=['POST'])
def save_message751():
    data = request.json
    username = data.get('username', '')
    message = data.get('message', '')

    if not username:
        return jsonify({'success': False, 'message': 'Username is required'})

    file_path = os.path.join(MESSAGE_DIR, f"{username}.txt")

    with open(file_path, "w") as file:
        file.write(message)

    return jsonify({'success': True, 'message': 'Message saved successfully'})

CART_DIR = "cart"  # Folder where user carts are stored
# Ensure cart directory exists
os.makedirs(CART_DIR, exist_ok=True)
# 🔹 Utility Function: Load Cart from File
def load_cart(username):
    cart_file = os.path.join(CART_DIR, f"{username}.txt")
    if os.path.exists(cart_file):
        with open(cart_file, "r") as f:
            return json.load(f)
    return []  # Return empty cart if file doesn't exist


# 🔹 Utility Function: Save Cart to File
def save_cart(username, cart_items):
    cart_file = os.path.join(CART_DIR, f"{username}.txt")
    with open(cart_file, "w") as f:
        json.dump(cart_items, f)

# 🛒 Adjust Cart Items to Available Stock
@app.route('/adjust-out-of-stock', methods=['POST'])
def adjust_out_of_stock():
    username = session.get("username", "Guest")
    if username == "Guest":
        return jsonify({'success': False, 'message': 'You need to log in!'})

    cart = load_cart(username)
    products = load_products()
    adjusted_cart = []

    for item in cart:
        product = next((p for category in products.values() for p in category if p[0] == item['product_id']), None)

        if product:
            try:
                available_stock = int(product[5])
            except:
                available_stock = float(product[5])  # Handle float stock if necessary

            if available_stock > 0:
                item['quantity'] = min(item['quantity'], available_stock)  # Reduce quantity to max available
                adjusted_cart.append(item)

    save_cart(username, adjusted_cart)

    return jsonify({'success': True, 'message': 'Cart updated with available stock!'})


# 🛒 Add to Cart (File-Based)
@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    username = session.get("username", "Guest")
    if username == "Guest":
        return jsonify({'success': False, 'message': 'You need to log in to add items to cart'})

    data = request.get_json()
    product_id = int(data['id'])
    try:
        quantity = int(data['order_quantity'])
    except:
        quantity = float(data['order_quantity'])
    message = data['order_Message']
    productName = data['product_name']
    productCat = data['product_cat']
    with open(f"messages/{username}.txt", "a") as f:
                f.write(f"ID: {product_id} | Name: {productName} | Category: {productCat} | Quantity: {quantity} \n \n \n")



    cart = load_cart(username)

    # Check if item exists
    item_exists = False
    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] += quantity
            item['message'] = message
            item_exists = True
            break

    # Add new item if not exists
    if not item_exists:
        cart.append({
            'product_id': product_id,
            'product_name': data['product_name'],  # Store product name
            'product_cat': data['product_cat'],
            'quantity': quantity,
            'message': message
        })

    save_cart(username, cart)  # Save to file

    return jsonify({'success': True})


# 🛒 View Cart
@app.route('/view-cart', methods=['GET'])
def view_cart():
    username = session.get("username", "Guest")
    if username == "Guest":
        return jsonify([])

    cart = load_cart(username)
    return jsonify(cart)


# 🛒 Update Cart Quantity & Message
@app.route('/update-cart', methods=['POST'])
def update_cart():
    username = session.get("username", "Guest")
    if username == "Guest":
        return jsonify({'success': False, 'message': 'You need to log in to update cart'})

    data = request.get_json()
    product_id = int(data['id'])
    try:
        quantity = int(data['order_quantity'])
    except:
        quantity = float(data['order_quantity'])

    message = data['order_Message']

    cart = load_cart(username)

    for item in cart:
        if item['product_id'] == product_id:
            if quantity > 0:
                item['quantity'] = quantity
                item['message'] = message
            else:
                cart.remove(item)  # Remove if quantity is 0

    save_cart(username, cart)  # Save updated cart

    return jsonify({'success': True})


# 🛒 Clear Cart
@app.route('/clear-cart', methods=['POST'])
def clear_cart():
    username = session.get("username", "Guest")
    if username == "Guest":
        return jsonify({'success': False, 'message': 'You need to log in to clear cart'})

    cart_file = os.path.join(CART_DIR, f"{username}.txt")

    if os.path.exists(cart_file):
        os.remove(cart_file)  # Delete the cart file

    return jsonify({'success': True, 'message': 'Cart has been cleared!'})


# 🚀 Submit Cart & Place Order
@app.route('/submit-cart', methods=['POST'])
def submit_cart():
    username = session.get("username", "Guest")
    if username == "Guest":
        return jsonify({'success': False, 'message': 'You need to log in to place an order'})

    cart = load_cart(username)
    if not cart:
        return jsonify({'success': False, 'message': 'Cart is empty'})

    products = load_products()  # Load available products
    failed_orders = []  # Stores items that couldn't be ordered due to stock issues
    successful_orders = []  # Stores successfully ordered products
    insufficient_stock = []  # Stores messages about insufficient stock

    for item in cart:
        product_id = item['product_id']
        quantity = item['quantity']
        message = item['message']

        # Find the product in available stock
        for category, items in products.items():
            for product in items:
                if product[0] == product_id:
                    try:
                        available_stock = int(product[5])
                    except:
                        available_stock = float(product[5])  # Handle float stock if necessary

                    if available_stock == 0:
                        insufficient_stock.append(f"{product[1]} (Out of stock)")
                        failed_orders.append(item)
                        continue

                    if quantity > available_stock:
                        insufficient_stock.append(f"{product[1]} (Only {available_stock} available)")
                        failed_orders.append(item)
                        continue

                    # Deduct stock and save
                    product[5] = str(available_stock - quantity)
                    save_products(products)

                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    with open("data/Orders.txt", "a") as order_file:
                        order_file.write(f"{current_time} | {username},{product_id},{quantity},{product[1]},{product[2]},{message}\n")

                    with open("data/OrderHistory.txt", "a") as order_file:
                        order_file.write(f"{current_time} | {username},{product_id},{quantity},{product[1]},{product[2]},{message}\n")

                    successful_orders.append(item)  # Add to successful orders

    # 🛒 **Update cart with only failed orders**
    save_cart(username, failed_orders)  # Keep only items that couldn’t be ordered

    if insufficient_stock:
        return jsonify({'success': False, 'message': f"Insufficient stock for: {', '.join(insufficient_stock)}"})

    return jsonify({'success': True, 'message': 'Order placed successfully!'})



# 🔥 Remove Out-of-Stock Items
@app.route('/remove-out-of-stock', methods=['POST'])
def remove_out_of_stock():
    username = session.get("username", "Guest")
    if username == "Guest":
        return jsonify({'success': False, 'message': 'You need to log in'})

    cart = load_cart(username)
    products = load_products()
    updated_cart = []
    removed_items = []

    for item in cart:
        product = next((p for category in products.values() for p in category if p[0] == item['product_id']), None)
        
        try:
            if product and int(product[5]) > 0:
                updated_cart.append(item)
            else:
                removed_items.append(product[1])
        except:
            if product and float(product[5]) > 0:
                updated_cart.append(item)
            else:
                removed_items.append(product[1])

    save_cart(username, updated_cart)

    if removed_items:
        return jsonify({'success': True, 'message': f"Removed out-of-stock items: {', '.join(removed_items)}"})
    else:
        return jsonify({'success': False, 'message': 'No out-of-stock items found.'})



@app.route('/delete-order2', methods=['POST'])
def delete_order2():
    data = request.get_json()
    product_id = int(data['productId'])
    try:
        order_quantity = int(data['orderQuantity'])
    except:
        order_quantity = float(data['orderQuantity'])

    # Load orders
    if os.path.exists("data/Orders.txt"):
        with open("data/Orders.txt", "r") as f:
            orders = [line.strip().split(",") for line in f]
    else:
        return jsonify({"success": False})

    # Filter out the order to delete
    try:
        updated_orders = [order for order in orders if not (int(order[1]) == product_id and int(order[2]) == order_quantity)]
    except:
        updated_orders = [order for order in orders if not (float(order[1]) == product_id and float(order[2]) == order_quantity)]
    
    # Write updated orders back to Orders.txt
    with open("data/Orders.txt", "w") as f:
        for order in updated_orders:
            f.write(",".join(order) + "\n")

    # Load products
    products = load_products()

    # Find the product and update its quantity
    for category, items in products.items():
        for product in items:
            if int(product[0]) == product_id:
                try:
                    product_quantity = int(product[5]) + order_quantity
                except:
                    product_quantity = float(product[5]) + order_quantity
                product[5] = str(product_quantity)  # Update the quantity
                
                # Save updated products
                save_products(products)
                break
    
    return jsonify({"success": True})


@app.route('/delete-order', methods=['POST'])
def delete_order():
    data = request.json  # Get the JSON data from the request
    order_to_delete = data.get('order')  # The exact order entry to delete

    if not order_to_delete:
        return jsonify({'error': 'Invalid order data'}), 400

    try:
        # Read the current orders
        with open('data/Orders.txt', 'r') as f:
            lines = f.readlines()

        # Write back all orders except the one to be deleted
        with open('data/Orders.txt', 'w') as f:
            for line in lines:
                if line.strip() != order_to_delete:  # Skip the order to delete
                    f.write(line)

        return jsonify({'success': True, 'message': 'Order deleted successfully'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get-out-of-stock-products', methods=['GET'])
def get_out_of_stock_products():
    try:
        products = load_products()
        out_of_stock = []

        for category, items in products.items():
            for product in items:
                try:
                    if int(product[5]) == 0:  # Check if quantity is 0
                        out_of_stock.append({
                            "id": product[0],
                            "name": product[1],
                            "category": product[2]
                        })
                except:
                    if float(product[5]) == 0:  # Check if quantity is 0
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
    username = session.get("username", "Guest")

    # Get the current time in Ireland timezone
    ireland_tz = pytz.timezone('Europe/Dublin')
    current_time = datetime.now(ireland_tz).strftime('%Y-%m-%d %H:%M:%S')

    # Save the notification details to notify.txt with timestamp
    notification_message = f"{current_time} : {username} asked for more stocks of Product ID: {product_id}\n"
    with open("data/notify.txt", "a") as f:
        f.write(notification_message)

    return redirect(url_for('client'))


@app.route('/place-order', methods=['POST'])
def place_order():
    products = load_products()  # Load products from your product database
    product_id = request.form.get('id')  # Safely retrieve product ID
    order_quantity = request.form.get('order_quantity')  # Safely retrieve quantity
    order_message = request.form.get('order_Message')  # Safely retrieve message
    username = session.get("username", "Guest")  # Get logged-in username from session

    # If product ID or order quantity is missing, return error
    if not product_id or not order_quantity:
        return render_template(
            "client.html",
            products=products,
            message="Invalid product or quantity.",
            message_type="error",
            username=username
        )

    product_id = int(product_id)
    try:
        order_quantity = int(order_quantity)
    except:
        order_quantity = float(order_quantity)

    # If user is not logged in, return error
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
    orders = []
    if os.path.exists("data/Orders.txt"):
        with open("data/Orders.txt", "r") as f:
            orders = [line.strip().split(",") for line in f]

    user_orders = [order for order in orders if order[0] == username]

    # Locate the product by ID
    for category, items in products.items():
        for product in items:
            if product[0] == product_id:
                try:
                    available_quantity = int(product[5])  # Quantity is at index 5
                except:
                    available_quantity = float(product[5])  # Quantity is at index 5
                if order_quantity > available_quantity:
                    return render_template(
                        "client.html",
                        products=products,
                        message="Insufficient stock for the selected product.",
                        message_type="error",
                        user_orders=user_orders,
                        username=username
                    )

                # Update product quantity in-memory (and save it later)
                product[5] = str(available_quantity - order_quantity)

                # Save updated products back to the products file
                save_products(products)

                # Create timestamp for the order
                ireland_tz = pytz.timezone('Europe/Dublin')
                current_time = datetime.now(ireland_tz).strftime('%Y-%m-%d %H:%M:%S')

                # Log the order in the Orders.txt
                with open("data/Orders.txt", "a") as order_file:
                    order_file.write(f"{current_time} | {username},{product_id},{order_quantity},{product[1]},{product[2]},{order_message}\n")
                
                # Log the order in the OrderHistory.txt (same format)
                with open("data/OrderHistory.txt", "a") as order_file:
                    order_file.write(f"{current_time} | {username},{product_id},{order_quantity},{product[1]},{product[2]},{order_message}\n")

                # Update user order history with the new order
                user_orders.append([current_time, username, str(product_id), str(order_quantity), product[1], product[2], str(order_message)])

                return render_template(
                    "client.html",
                    products=products,
                    show_login_popup=False,
                    message="Order placed successfully!",
                    message_type="success",
                    user_orders=user_orders,
                    username=username
                )

    # If the product is not found, return error
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
