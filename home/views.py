from django.shortcuts import redirect, render, get_object_or_404
from django.http import HttpResponseBadRequest, JsonResponse, QueryDict
from django.conf import settings 
from django.urls import reverse
import stripe 
from decimal import Decimal, InvalidOperation # <-- ADDED
from urllib.parse import urlparse, urlunparse # <-- ADDED

# <-- ADDED PrintSizePrice
from .models import ProductPage, Order, OrderItem, IndexShopPage, PrintSizePrice 
from .forms import OrderCreateForm 

# NEW imports for login/logout
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages

# --- Cart Views (Corrected) ---

def add_to_cart(request, product_id):
    """
    Adds a product to the session cart with specific size and frame options.
    This view now expects a POST request.
    """
    if request.method != 'POST':
        return HttpResponseBadRequest("This view only accepts POST requests.")

    cart = request.session.get('cart', {})

    # === NEUE LOGIK (FIX FÜR PROBLEM 1) ===
    try:
        product = ProductPage.objects.get(id=product_id)
        
        # Get data from the form
        size_id = request.POST.get('size_variant')
        add_frame_str = request.POST.get('add_frame', 'false')
        add_frame = (add_frame_str == 'true')
        quantity = int(request.POST.get('quantity', 1))

        if not size_id:
            messages.error(request, "Please select a size.")
            return redirect(request.META.get('HTTP_REFERER', '/'))

        # Get the price snippet object
        size_price_obj = PrintSizePrice.objects.get(id=size_id)

    except (ProductPage.DoesNotExist, PrintSizePrice.DoesNotExist):
        messages.error(request, "Product or size not found.")
        return redirect(request.META.get('HTTP_REFERER', '/'))
    except (ValueError, TypeError):
        quantity = 1  
    
    # Create a unique key for this exact configuration
    # e.g., "12_5_true" (ProductID 12, SizeID 5, Framed)
    cart_key = f"{product_id}_{size_id}_{add_frame}"

    # Calculate the final price for *one* item
    final_price = size_price_obj.base_price
    if add_frame:
        final_price += size_price_obj.frame_addon_price

    if cart_key in cart:
        # Item already in cart, just increase quantity
        cart[cart_key]['quantity'] += quantity
    else:
        # New item, add all details
        cart[cart_key] = {
            'product_id': product.id,
            'product_title': product.title,
            'size_id': size_id,
            'size_name': size_price_obj.size_name,
            'framed': add_frame,
            'quantity': quantity,
            'price': str(final_price) # Store price at time of adding
        }

    request.session['cart'] = cart
    request.session.modified = True
    messages.success(request, f"Added {product.title} to cart.")
    
    # === NEUE LOGIK (FIX FÜR PROBLEM 2) ===
    # Redirect back to the same page, but add query parameters
    # so the JavaScript can re-select the user's options.
    
    referer_url = request.META.get('HTTP_REFERER', '/')
    
    parsed_url = urlparse(referer_url)
    query_dict = QueryDict(parsed_url.query, mutable=True)
    query_dict['size'] = size_id
    query_dict['frame'] = add_frame_str
    
    new_query_string = query_dict.urlencode()
    new_url = urlunparse((
        parsed_url.scheme, 
        parsed_url.netloc, 
        parsed_url.path, 
        parsed_url.params, 
        new_query_string, 
        parsed_url.fragment
    ))
    
    return redirect(new_url)


def remove_one_from_cart(request, product_id):
    """
    Reduces the quantity of an item in the cart by 1.
    NOTE: This now expects 'product_id' to be the 'cart_key'
    This view may need updating depending on how you link to it.
    For simplicity, this example assumes product_id is the cart_key.
    """
    cart = request.session.get('cart', {})
    cart_key = str(product_id) # Assuming product_id is the cart_key

    if cart_key in cart:
        cart[cart_key]['quantity'] -= 1
        if cart[cart_key]['quantity'] <= 0:
            del cart[cart_key]
    
    request.session['cart'] = cart
    request.session.modified = True
    
    return redirect(request.META.get('HTTP_REFERER', '/'))

# --- Checkout & Payment Views ---

def checkout_page(request):
    """
    Handles the Address Form (Step 1 of checkout).
    """
    cart_session = request.session.get('cart', {})
    if not cart_session:
        messages.error(request, "Your cart is empty.")
        shop_page = IndexShopPage.objects.live().first()
        if shop_page:
            return redirect(shop_page.url)
        return redirect('/') 

    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        
        if form.is_valid():
            # Save address data to session, don't create Order yet
            request.session['order_data'] = form.cleaned_data
            return redirect(reverse('payment')) 
            
    else:
        # Pre-fill form if user is logged in
        if request.user.is_authenticated:
            initial_data = {
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
            }
            form = OrderCreateForm(initial=initial_data)
        else:
            form = OrderCreateForm()
        
    return render(request, 'home/checkout.html', {'form': form})

# home/views.py

# ... (Keep imports and top part: add_to_cart, remove_one_from_cart) ...

# --- NEW: Helper for Country Codes ---
def get_eu_country_codes():
    return [
        'BE', 'BG', 'CZ', 'DK', 'DE', 'EE', 'IE', 'EL', 'ES', 'FR', 'HR', 'IT', 
        'CY', 'LV', 'LT', 'LU', 'HU', 'MT', 'NL', 'AT', 'PL', 'PT', 'RO', 'SI', 
        'SK', 'FI', 'SE'
    ]

# --- REPLACES checkout_page AND payment_page ---
def checkout_page(request):
    """
    Single-step Checkout using Stripe Embedded Checkout.
    Calculates shipping rules and lets Stripe handle address/payment.
    """
    cart_session = request.session.get('cart', {})
    if not cart_session:
        messages.error(request, "Your cart is empty.")
        return redirect('/')

    # 1. Analyze Cart for Shipping Rules
    product_total = 0
    total_quantity = 0
    has_a2 = False
    has_frame = False
    
    stripe_line_items = []
    
    # Filter for valid product IDs
    real_ids = [k.split('_')[0] for k in cart_session.keys()]
    products = ProductPage.objects.filter(id__in=real_ids)
    product_map = {str(p.id): p for p in products}

    for cart_key, item_data in cart_session.items():
        if isinstance(item_data, dict):
            qty = int(item_data['quantity'])
            # We need a price in CENTS for Stripe
            price_float = float(item_data['price'])
            price_cents = int(price_float * 100)
            
            size_name = item_data.get('size_name', '')
            is_framed = item_data.get('framed', False)
            
            if 'A2' in size_name.upper(): has_a2 = True
            if is_framed: has_frame = True
            
            # Create Line Item for Stripe
            stripe_line_items.append({
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f"{item_data['product_title']} ({size_name})",
                        'description': "Framed" if is_framed else "Print Only",
                        # Optional: Add images here if you have absolute URLs
                    },
                    'unit_amount': price_cents,
                },
                'quantity': qty,
            })
            
            product_total += price_float * qty
            total_quantity += qty

    # 2. Define Shipping Rates based on your Rules
    
    # --- Austria Rules ---
    # Free if: >1 item OR A2 OR Framed. Else 4.90
    austria_price = 490 # 4.90 in cents
    if total_quantity > 1 or has_a2 or has_frame:
        austria_price = 0
        
    # --- International Base Rules ---
    # Base EU Rate
    if has_a2:
        eu_price = 1590 # 15.90
    else:
        eu_price = 1290 # 12.90

    # Switzerland (+5.00)
    ch_price = eu_price + 500 
    
    # World (+15.00)
    world_price = eu_price + 1500

    # 3. Create Stripe Session
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    try:
        session = stripe.checkout.Session.create(
            ui_mode='embedded',
            line_items=stripe_line_items,
            mode='payment',
            return_url=f"{request.scheme}://{request.get_host()}{reverse('checkout_success')}?session_id={{CHECKOUT_SESSION_ID}}",
            
            # Enable Address Collection
            shipping_address_collection={
                'allowed_countries': ['AT', 'DE', 'CH', 'FR', 'IT', 'US', 'GB', 'CA', 'AU'] # Add more as needed
            },
            
            # Dynamic Shipping Options
            shipping_options=[
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': austria_price, 'currency': 'eur'},
                        'display_name': 'Shipping (Austria)',
                        'delivery_estimate': {'minimum': {'unit': 'business_day', 'value': 2}, 'maximum': {'unit': 'business_day', 'value': 4}},
                    },
                    # APPLY ONLY TO AUSTRIA
                    'shipping_address_collection_option': {'allowed_countries': ['AT']} 
                },
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': eu_price, 'currency': 'eur'},
                        'display_name': 'Shipping (EU)',
                        'delivery_estimate': {'minimum': {'unit': 'business_day', 'value': 5}, 'maximum': {'unit': 'business_day', 'value': 10}},
                    },
                    # APPLY TO EU COUNTRIES (excluding AT)
                    'shipping_address_collection_option': {'allowed_countries': [c for c in get_eu_country_codes() if c != 'AT']}
                },
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': ch_price, 'currency': 'eur'},
                        'display_name': 'Shipping (Switzerland)',
                        'delivery_estimate': {'minimum': {'unit': 'business_day', 'value': 5}, 'maximum': {'unit': 'business_day', 'value': 10}},
                    },
                    'shipping_address_collection_option': {'allowed_countries': ['CH']}
                },
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': world_price, 'currency': 'eur'},
                        'display_name': 'International Shipping',
                        'delivery_estimate': {'minimum': {'unit': 'business_day', 'value': 10}, 'maximum': {'unit': 'business_day', 'value': 20}},
                    },
                    # Apply to major non-EU countries (Add others to 'allowed_countries' above too)
                    'shipping_address_collection_option': {'allowed_countries': ['US', 'GB', 'CA', 'AU']}
                },
            ],
            
            # Metadata for your backend
            metadata={
                'cart_key_list': ",".join(cart_session.keys())
            }
        )
    except Exception as e:
        messages.error(request, f"Error connecting to checkout: {e}")
        return redirect('/')

    return render(request, 'home/checkout.html', {
        'client_secret': session.client_secret,
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY
    })


def checkout_success(request):
    """
    Handles success return from Stripe. 
    Fetches session details to create the Order in Django.
    """
    session_id = request.GET.get('session_id')
    cart_session = request.session.get('cart', {})

    if not session_id:
        return redirect('/')

    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    try:
        # Retrieve Session to get customer details
        session = stripe.checkout.Session.retrieve(session_id)
        customer_details = session.customer_details
        shipping_details = session.shipping_details
        
        # Create Order in Database
        order = Order.objects.create(
            first_name=customer_details.name.split(' ')[0] if customer_details.name else "Guest",
            last_name=" ".join(customer_details.name.split(' ')[1:]) if customer_details.name else "",
            email=customer_details.email,
            address=f"{shipping_details.address.line1} {shipping_details.address.line2 or ''}",
            postal_code=shipping_details.address.postal_code,
            city=shipping_details.address.city,
            country=shipping_details.address.country,
            stripe_pid=session.payment_intent,
            paid=True,
            user=request.user if request.user.is_authenticated else None
        )

        # Create Order Items
        real_ids = [key.split('_')[0] for key in cart_session.keys()]
        products = ProductPage.objects.filter(id__in=real_ids)
        product_map = {str(p.id): p for p in products}

        for cart_key, item_data in cart_session.items():
            if isinstance(item_data, dict):
                product = product_map.get(str(item_data['product_id']))
                if product:
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        price=item_data['price'],
                        quantity=item_data['quantity'],
                        size_name=item_data.get('size_name', ''),
                        framed=item_data.get('framed', False)
                    )

        # Clear Cart
        if 'cart' in request.session:
            del request.session['cart']
        request.session.modified = True
        
        return render(request, 'home/checkout_done.html', {'order': order})

    except Exception as e:
        return HttpResponseBadRequest(f"Error processing order: {str(e)}")


# ... (Keep checkout_done_page logic if needed, or remove if unused) ...
# ... (Keep auth views) ...