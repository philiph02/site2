import json
import stripe
from django.shortcuts import redirect, render
from django.http import HttpResponseBadRequest, JsonResponse
from django.conf import settings 
from django.urls import reverse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm

from .models import ProductPage, Order, OrderItem, PrintSizePrice

# --- Helper: Country Lists ---
def get_eu_countries():
    return ['BE', 'BG', 'CZ', 'DK', 'DE', 'EE', 'IE', 'GR', 'ES', 'FR', 'HR', 'IT', 'CY', 'LV', 'LT', 'LU', 'HU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SI', 'SK', 'FI', 'SE']

def get_europe_non_eu():
    return ['CH', 'GB', 'NO', 'IS', 'LI', 'AL', 'AD', 'BA', 'ME', 'MK', 'RS', 'TR']

def get_world_countries():
    return ['US', 'CA', 'AU', 'NZ', 'JP', 'SG', 'AE', 'QA', 'KR']

# --- Cart Views ---
def add_to_cart(request, product_id):
    try: product = ProductPage.objects.get(id=product_id)
    except: return HttpResponseBadRequest("Product not found")
    cart = request.session.get('cart', {})
    quantity = int(request.POST.get('quantity', 1))
    size_id = request.POST.get('size_variant')
    add_frame = (request.POST.get('add_frame', 'false') == 'true')
    
    size_name, price_to_add = "Standard", product.price 
    if size_id:
        try:
            v = PrintSizePrice.objects.get(id=size_id)
            size_name, price_to_add = v.size_name, v.base_price
            if add_frame: price_to_add += v.frame_addon_price
        except: pass

    cart_key = f"{product.id}_{size_id}_{add_frame}"
    if cart_key in cart:
        cart[cart_key]['quantity'] += quantity
    else:
        cart[cart_key] = {'product_id': product.id, 'product_title': product.title, 'size_name': size_name, 'framed': add_frame, 'quantity': quantity, 'price': str(price_to_add)}
    
    request.session['cart'] = cart
    request.session.modified = True
    messages.success(request, f"Added {product.title} to cart")
    return redirect(request.META.get('HTTP_REFERER', '/'))

def remove_one_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    if product_id in cart: del cart[product_id]
    request.session['cart'] = cart
    request.session.modified = True
    return redirect(request.META.get('HTTP_REFERER', '/'))


# --- 1. Checkout Page (Start) ---
def checkout_page(request):
    cart_session = request.session.get('cart', {})
    if not cart_session:
        messages.error(request, "Your cart is empty.")
        return redirect('/')

    stripe_line_items = []
    for k, item in cart_session.items():
        if isinstance(item, dict):
            stripe_line_items.append({
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': f"{item['product_title']} ({item.get('size_name')})"},
                    'unit_amount': int(float(item['price']) * 100),
                },
                'quantity': int(item['quantity']),
            })

    stripe.api_key = settings.STRIPE_SECRET_KEY
    all_allowed = ['AT'] + get_eu_countries() + get_europe_non_eu() + get_world_countries()

    try:
        session = stripe.checkout.Session.create(
            ui_mode='embedded',
            line_items=stripe_line_items,
            mode='payment',
            return_url=f"{request.scheme}://{request.get_host()}{reverse('checkout_success')}?session_id={{CHECKOUT_SESSION_ID}}",
            allow_promotion_codes=True,
            shipping_address_collection={'allowed_countries': all_allowed},
            
            # This tells Stripe: "Ask my server for the price when address changes"
            permissions={'update_shipping_details': 'server_only'},
            
            # Initial dummy option (will be updated immediately by JS)
            shipping_options=[{
                'shipping_rate_data': {
                    'type': 'fixed_amount',
                    'fixed_amount': {'amount': 0, 'currency': 'eur'},
                    'display_name': 'Calculating...',
                }
            }]
        )
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect('/')

    return render(request, 'home/checkout.html', {
        'client_secret': session.client_secret,
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY
    })


# --- 2. Shipping Calculator (The Fix) ---
@csrf_exempt
def calculate_shipping_options(request):
    """
    Called by Stripe JS when address changes.
    Calculates the price and updates the Stripe Session.
    """
    if request.method != 'POST': return JsonResponse({'error': 'POST required'}, status=400)
    
    try:
        data = json.loads(request.body)
        session_id = data.get('checkout_session_id')
        shipping_details = data.get('shipping_details') or {}
        address = shipping_details.get('address') or {}
        country = address.get('country')

        # 1. Analyze Cart (A2 / Framed logic)
        cart_session = request.session.get('cart', {})
        has_heavy_item = False
        for k, item in cart_session.items():
            if isinstance(item, dict):
                size = item.get('size_name', '')
                framed = item.get('framed', False)
                if 'A2' in str(size).upper() or framed:
                    has_heavy_item = True

        # 2. Determine Price
        price_cents = 2990 
        label = "International Shipping"

        if country == 'AT':
            if has_heavy_item:
                price_cents = 0
                label = "Free Shipping (Austria)"
            else:
                price_cents = 490
                label = "Standard Shipping (Austria)"
                
        elif country in get_eu_countries():
            price_cents = 1690 if has_heavy_item else 1290
            label = "Standard Shipping (EU)"
            
        elif country in get_europe_non_eu():
            price_cents = 1990
            label = "Shipping (Europe Non-EU)"
            
        elif country in get_world_countries():
            price_cents = 2990
            label = "International Shipping"

        # 3. Update Stripe Session (FIX: Removed shipping_details)
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        stripe.checkout.Session.modify(
            session_id,
            shipping_options=[{
                'shipping_rate_data': {
                    'type': 'fixed_amount',
                    'fixed_amount': {'amount': price_cents, 'currency': 'eur'},
                    'display_name': label,
                }
            }]
        )
        
        return JsonResponse({'type': 'accept'})

    except Exception as e:
        print(f"CALC ERROR: {e}")
        return JsonResponse({'type': 'reject', 'errorMessage': str(e)})


# --- 3. Success View ---
def checkout_success(request):
    session_id = request.GET.get('session_id')
    if not session_id: return redirect('/')
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        if Order.objects.filter(stripe_pid=session.payment_intent).exists():
            order = Order.objects.get(stripe_pid=session.payment_intent)
            return render(request, 'home/checkout_done.html', {'order': order})

        cust = session.customer_details
        ship = session.shipping_details or cust
        order = Order.objects.create(
            first_name=cust.name.split()[0] if cust.name else "Guest",
            last_name=" ".join(cust.name.split()[1:]) if cust.name else "",
            email=cust.email,
            address=f"{ship.address.line1}, {ship.address.city}",
            postal_code=ship.address.postal_code, city=ship.address.city, country=ship.address.country,
            stripe_pid=session.payment_intent, paid=True
        )
        
        cart = request.session.get('cart', {})
        real_ids = [k.split('_')[0] for k in cart.keys()]
        products = {str(p.id): p for p in ProductPage.objects.filter(id__in=real_ids)}
        
        for k, item in cart.items():
            if isinstance(item, dict) and str(item['product_id']) in products:
                OrderItem.objects.create(order=order, product=products[str(item['product_id'])], price=item['price'], quantity=item['quantity'], size_name=item.get('size_name', ''), framed=item.get('framed'))

        request.session['cart'] = {}
        return render(request, 'home/checkout_done.html', {'order': order})
    except Exception as e:
        return HttpResponseBadRequest(f"Error: {e}")

def login_view(request): return redirect('/')
def logout_view(request): return redirect('/')