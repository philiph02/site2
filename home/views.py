from django.shortcuts import redirect, render
from django.http import HttpResponseBadRequest
from django.conf import settings 
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
import stripe 

from .models import ProductPage, Order, OrderItem, PrintSizePrice

# --- Helper: Country Lists ---

def get_eu_countries():
    """Returns list of EU country codes (excluding Austria)."""
    # FIXED: 'GR' is the correct Stripe code for Greece
    return [
        'BE', 'BG', 'CZ', 'DK', 'DE', 'EE', 'IE', 'GR', 'ES', 'FR', 'HR', 'IT', 
        'CY', 'LV', 'LT', 'LU', 'HU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SI', 
        'SK', 'FI', 'SE'
    ]

def get_europe_non_eu():
    """Returns Non-EU European countries (Switzerland, UK, Norway, etc.)"""
    return [
        'CH', 'GB', 'NO', 'IS', 'LI', 'AL', 'AD', 'BA', 'ME', 'MK', 'RS', 'TR'
    ]

def get_world_countries():
    """Returns major international shipping destinations."""
    return ['US', 'CA', 'AU', 'NZ', 'JP', 'SG', 'AE', 'QA', 'KR']

# --- Cart Views ---

def add_to_cart(request, product_id):
    try:
        product = ProductPage.objects.get(id=product_id)
    except ProductPage.DoesNotExist:
        return HttpResponseBadRequest("Product not found")

    cart = request.session.get('cart', {})
    quantity = 1
    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            quantity = 1
            
    size_id = request.POST.get('size_variant')
    add_frame_str = request.POST.get('add_frame', 'false')
    add_frame = (add_frame_str == 'true')
    
    size_name = "Standard"
    price_to_add = product.price 
    
    if size_id:
        try:
            variant = PrintSizePrice.objects.get(id=size_id)
            size_name = variant.size_name
            price_to_add = variant.base_price
            if add_frame:
                price_to_add += variant.frame_addon_price
        except PrintSizePrice.DoesNotExist:
            pass

    cart_key = f"{product.id}_{size_id}_{add_frame}"
    
    if cart_key in cart:
        cart[cart_key]['quantity'] += quantity
    else:
        cart[cart_key] = {
            'product_id': product.id,
            'product_title': product.title,
            'size_name': size_name,
            'framed': add_frame,
            'quantity': quantity,
            'price': str(price_to_add)
        }

    request.session['cart'] = cart
    request.session.modified = True
    messages.success(request, f"Added {product.title} to cart")
    return redirect(request.META.get('HTTP_REFERER', '/'))


def remove_one_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    if product_id in cart:
        del cart[product_id]
    request.session['cart'] = cart
    request.session.modified = True
    return redirect(request.META.get('HTTP_REFERER', '/'))


# --- Checkout View (Stripe Embedded) ---

def checkout_page(request):
    cart_session = request.session.get('cart', {})
    if not cart_session:
        messages.error(request, "Your cart is empty.")
        return redirect('/')

    # 1. Analyze Cart for Shipping Logic
    has_heavy_item = False # True if A2 or Framed
    stripe_line_items = []
    
    # Extract real IDs
    real_ids = [k.split('_')[0] for k in cart_session.keys()]

    for cart_key, item_data in cart_session.items():
        if isinstance(item_data, dict):
            qty = int(item_data['quantity'])
            price_float = float(item_data['price'])
            price_cents = int(price_float * 100)
            
            size_name = item_data.get('size_name', '')
            is_framed = item_data.get('framed', False)
            
            # Logic: A2 or Framed triggers higher shipping
            if 'A2' in str(size_name).upper() or is_framed: 
                 has_heavy_item = True
            
            stripe_line_items.append({
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f"{item_data['product_title']} ({size_name})",
                        'description': "Framed" if is_framed else "Print Only",
                    },
                    'unit_amount': price_cents,
                },
                'quantity': qty,
            })

    # 2. Calculate Prices (in Cents)
    
    # Austria: 4.90 EUR (Free if Heavy/Framed)
    price_at = 0 if has_heavy_item else 490

    # EU: 12.90 EUR (16.90 EUR if Heavy/Framed)
    price_eu = 1690 if has_heavy_item else 1290

    # Non-EU Europe: 19.90 EUR Flat
    price_non_eu = 1990

    # World: 29.90 EUR Flat
    price_world = 2990


    # 3. Create Stripe Session
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    # Allowed countries for the address form
    all_allowed_countries = ['AT'] + get_eu_countries() + get_europe_non_eu() + get_world_countries()

    try:
        session = stripe.checkout.Session.create(
            ui_mode='embedded',
            line_items=stripe_line_items,
            mode='payment',
            return_url=f"{request.scheme}://{request.get_host()}{reverse('checkout_success')}?session_id={{CHECKOUT_SESSION_ID}}",
            
            # Enable Discount Codes
            allow_promotion_codes=True,

            # Define where we ship to
            shipping_address_collection={
                'allowed_countries': all_allowed_countries
            },
            
            # Define Shipping Options (Simplified)
            # The user will see these 4 options and pick the right one.
            shipping_options=[
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': price_at, 'currency': 'eur'},
                        'display_name': 'Shipping to Austria',
                    }
                },
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': price_eu, 'currency': 'eur'},
                        'display_name': 'Shipping to EU',
                    }
                },
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': price_non_eu, 'currency': 'eur'},
                        'display_name': 'Shipping to Europe (Non-EU)',
                    }
                },
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': price_world, 'currency': 'eur'},
                        'display_name': 'International Shipping (World)',
                    }
                },
            ],
        )
    except Exception as e:
        print(f"STRIPE ERROR: {e}") # Check terminal for details
        messages.error(request, f"Error starting checkout: {e}")
        return redirect('/')

    return render(request, 'home/checkout.html', {
        'client_secret': session.client_secret,
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY
    })


def checkout_success(request):
    session_id = request.GET.get('session_id')
    cart_session = request.session.get('cart', {})

    if not session_id:
        return redirect('/')

    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        customer = session.customer_details
        shipping = session.shipping_details or customer
        
        order = Order.objects.create(
            first_name=customer.name.split(' ')[0] if customer.name else "Guest",
            last_name=" ".join(customer.name.split(' ')[1:]) if customer.name else "",
            email=customer.email,
            address=f"{shipping.address.line1}, {shipping.address.city}" if shipping.address else "N/A",
            postal_code=shipping.address.postal_code if shipping.address else "",
            city=shipping.address.city if shipping.address else "",
            country=shipping.address.country if shipping.address else "",
            stripe_pid=session.payment_intent,
            paid=True
        )

        real_ids = [k.split('_')[0] for k in cart_session.keys()]
        products = ProductPage.objects.filter(id__in=real_ids)
        product_map = {str(p.id): p for p in products}

        for key, item in cart_session.items():
            if isinstance(item, dict):
                prod = product_map.get(str(item['product_id']))
                if prod:
                    OrderItem.objects.create(
                        order=order,
                        product=prod,
                        price=item['price'],
                        quantity=item['quantity'],
                        size_name=item.get('size_name', ''),
                        framed=item.get('framed', False)
                    )

        request.session['cart'] = {}
        request.session.modified = True
        
        return render(request, 'home/checkout_done.html', {'order': order})

    except Exception as e:
        return HttpResponseBadRequest(f"Error: {str(e)}")

# --- Auth Views ---
def login_view(request): return redirect('/')
def logout_view(request): return redirect('/')