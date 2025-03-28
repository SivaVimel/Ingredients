import json

def reset_quantity(input_file, output_file):
    # Load JSON data from file
    with open(input_file, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Iterate through each category and product to set quantity (key[5]) to "0"
    for category, products in data.items():
        for product in products:
            product[5] = "0"  # Set the quantity to "0"

    # Save the modified data to a new JSON file
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

    print(f"Updated JSON saved as {output_file}")

# Example Usage
reset_quantity("data/Products.txt", "Updated_Product.txt")