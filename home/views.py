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
    return ['US', 'CA', 'AU', 'NZ', 'JP', 'SG', 'AE', 'QA', 'KR', 'CN', 'HK', 'IN']

# --- Helper: Calculate Shipping Cost ---
def calculate_cart_shipping(cart_session, country_code):
    """
    Central logic for shipping costs.
    Returns (price_in_cents, label_string)
    """
    has_heavy_item = False # A2 or Framed
    
    # Analyze Cart
    for k, item in cart_session.items():
        if isinstance(item, dict):
            size = item.get('size_name', '')
            framed = item.get('framed', False)
            if 'A2' in str(size).upper() or framed:
                has_heavy_item = True

    # Default
    price_cents = 2990 
    label = "International Shipping"

    if country_code == 'AT':
        if has_heavy_item:
            price_cents = 0
            label = "Free Shipping (Austria)"
        else:
            price_cents = 490
            label = "Standard Shipping (Austria)"
            
    elif country_code in get_eu_countries():
        if has_heavy_item:
            price_cents = 1690
            label = "Large Package Shipping (EU)"
        else:
            price_cents = 1290
            label = "Standard Shipping (EU)"
            
    elif country_code in get_europe_non_eu():
        price_cents = 1990
        label = "Shipping (Europe Non-EU)"
        
    elif country_code in get_world_countries():
        price_cents = 2990
        label = "International Shipping"
        
    return price_cents, label


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
    if product_id in cart: del cart[product_id]
    request.session['cart'] = cart
    request.session.modified = True
    return redirect(request.META.get('HTTP_REFERER', '/'))


# --- API: Update Shipping in Cart ---
@csrf_exempt
def update_cart_shipping(request):
    """
    Called by JS when user changes country in the Cart.
    Updates session and returns new totals.
    """
    if request.method != 'POST': return JsonResponse({'error': 'POST required'}, status=400)
    
    data = json.loads(request.body)
    country = data.get('country')
    
    # Save preference to session
    request.session['shipping_country'] = country
    request.session.modified = True
    
    # Calculate new costs
    cart = request.session.get('cart', {})
    shipping_cents, label = calculate_cart_shipping(cart, country)
    
    # Calculate Product Total
    product_total = 0
    for k, item in cart.items():
        if isinstance(item, dict):
            product_total += float(item['price']) * int(item['quantity'])
            
    total = product_total + (shipping_cents / 100)
    
    return JsonResponse({
        'shipping_cost': f"{shipping_cents/100:.2f}",
        'total': f"{total:.2f}",
        'label': label
    })


# --- Checkout View ---

def checkout_page(request):
    cart_session = request.session.get('cart', {})
    if not cart_session:
        messages.error(request, "Your cart is empty.")
        return redirect('/')

    # Get the country selected in the cart (Default AT)
    country = request.session.get('shipping_country', 'AT')

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

    # Calculate final shipping for Stripe
    shipping_cents, shipping_label = calculate_cart_shipping(cart_session, country)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.create(
            ui_mode='embedded',
            line_items=stripe_line_items,
            mode='payment',
            return_url=f"{request.scheme}://{request.get_host()}{reverse('checkout_success')}?session_id={{CHECKOUT_SESSION_ID}}",
            allow_promotion_codes=True,
            
            # Lock address collection to the selected country
            shipping_address_collection={'allowed_countries': [country]},
            
            # Pass the single, pre-calculated shipping option
            shipping_options=[{
                'shipping_rate_data': {
                    'type': 'fixed_amount',
                    'fixed_amount': {'amount': shipping_cents, 'currency': 'eur'},
                    'display_name': shipping_label,
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


# --- Success View ---
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
                OrderItem.objects.create(order=order, product=products[str(item['product_id'])], price=item['price'], quantity=item['quantity'], size_name=item.get('size_name', ''), framed=item.get('framed', False))

        request.session['cart'] = {}
        return render(request, 'home/checkout_done.html', {'order': order})
    except Exception as e:
        return HttpResponseBadRequest(f"Error: {e}")

def login_view(request): return redirect('/')
def logout_view(request): return redirect('/')