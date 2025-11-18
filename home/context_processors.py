from decimal import Decimal, InvalidOperation
from .models import ProductPage, HomePage, PhotographyPage, IndexShopPage 

# ======================================================================
# FIX FOR NAV LINKS
# ======================================================================
def global_nav_links(request):
    """
    Provides global navigation links to all templates.
    """
    try:
        about_page = HomePage.objects.live().first()
        photography_page = PhotographyPage.objects.live().first()
        index_shop_page = IndexShopPage.objects.live().first()
    except Exception:
        # Handle cases where pages might not exist or db isn't ready
        about_page = None
        photography_page = None
        index_shop_page = None

    return {
        'about_page': about_page,
        'photography_page': photography_page,
        # This key 'shop_page' MUST match your base.html
        'shop_page': index_shop_page,
    }

# ======================================================================
# FIX FOR CART CRASH (AttributeError & TypeError)
# ======================================================================
def cart_context(request):
    """
    Provides cart items, total quantity, and total price to all templates.
    Updated to read the new cart structure and match base.html.
    """
    cart_session = request.session.get('cart', {})
    
    total_price = Decimal(0)
    total_quantity = 0
    cart_items = [] # A list of the cart item dictionaries
    
    # --- FIX FOR 'int' object is not subscriptable ---
    # Filter session to only include new, valid cart items (dictionaries)
    valid_cart_items = {}
    for key, item in cart_session.items():
        if isinstance(item, dict) and 'product_id' in item and 'price' in item:
            valid_cart_items[key] = item
    
    # Get all product objects in one query
    product_ids = [item['product_id'] for item in valid_cart_items.values()]
    products = ProductPage.objects.filter(id__in=product_ids).specific()
    product_map = {str(p.id): p for p in products}

    # This loop is now safe
    for cart_key, item_details in valid_cart_items.items():
        try:
            # --- FIX FOR 'AttributeError' ---
            # Get price from session, NOT product.price
            price_per_item = Decimal(item_details['price'])
            quantity = int(item_details['quantity'])
            
            # Calculate totals
            total_price += price_per_item * quantity
            total_quantity += quantity

            product = product_map.get(str(item_details['product_id']))
            
            # Create the dict for the template
            item_data_for_template = {
                'product': product,
                'quantity': quantity,
                'cart_key': cart_key, # For the *correct* removal URL
                # Use 'item_total' to match base.html
                'item_total': (price_per_item * quantity).quantize(Decimal('0.01')),
                'price_per_item': price_per_item,
                'size_name': item_details.get('size_name', ''), # For cart display
                'framed': item_details.get('framed', False) # For cart display
            }
            
            if product:
                cart_items.append(item_data_for_template)

        except (InvalidOperation, TypeError, KeyError, ValueError):
            # Skip any malformed cart items
            continue

    return {
        'cart_items': cart_items,
        'cart_total_price': total_price,
        # Use 'cart_total_count' to match base.html
        'cart_total_count': total_quantity, 
    }