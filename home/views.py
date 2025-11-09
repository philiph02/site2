from django.shortcuts import redirect, render, get_object_or_404
from django.http import HttpResponseBadRequest, JsonResponse
from django.conf import settings 
from django.urls import reverse
import stripe 

from .models import ProductPage, Order, OrderItem, IndexShopPage # <-- ADDED IndexShopPage
from .forms import OrderCreateForm 

# NEW imports for login/logout
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages

# --- Cart Views (Corrected) ---

def add_to_cart(request, product_id):
    """
    Adds a product to the session cart.
    Takes quantity 1 (for GET) or form quantity (for POST).
    """
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
    
    product_id_str = str(product.id)
    
    if product_id_str in cart:
        cart[product_id_str] += quantity
    else:
        cart[product_id_str] = quantity

    request.session['cart'] = cart
    request.session.modified = True
    
    return redirect(request.META.get('HTTP_REFERER', '/'))


def remove_one_from_cart(request, product_id):
    """
    Reduces the quantity of an item in the cart by 1.
    """
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)

    if product_id_str in cart:
        cart[product_id_str] -= 1
        if cart[product_id_str] <= 0:
            del cart[product_id_str]
    
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


def payment_page(request):
    """
    Handles the Stripe Payment (Step 2 of checkout).
    """
    cart_session = request.session.get('cart', {})
    order_data = request.session.get('order_data')

    if not cart_session or not order_data:
        messages.error(request, "Your session has expired. Please start again.")
        return redirect(reverse('checkout'))

    # Get total price from cart_context logic
    total_price = 0
    product_ids = cart_session.keys()
    products = ProductPage.objects.filter(id__in=product_ids)
    product_map = {str(p.id): p for p in products}

    for product_id, quantity in cart_session.items():
        product = product_map.get(product_id)
        if product and quantity > 0:
            total_price += product.price * quantity

    total_price_cents = int(total_price * 100)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    try:
        intent = stripe.PaymentIntent.create(
            amount=total_price_cents,
            currency='eur',
            metadata={'order_data_email': order_data.get('email')} # Example metadata
        )
        client_secret = intent.client_secret
    except Exception as e:
        messages.error(request, f"Error contacting payment provider: {e}")
        return redirect(reverse('checkout'))

    context = {
        'client_secret': client_secret,
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY, 
        'total_price': total_price,
        'order': order_data # Pass address info to display on page
    }
    return render(request, 'home/checkout_payment.html', context)


def checkout_success(request):
    """
    This view is now called by JavaScript (fetch) when payment is confirmed.
    It creates the final order and returns a JSON response.
    """
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method.")

    cart_session = request.session.get('cart', {})
    order_data = request.session.get('order_data')
    
    import json
    try:
        data = json.loads(request.body)
        stripe_pid = data.get('stripe_pid')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)


    if not cart_session or not order_data or not stripe_pid:
        return JsonResponse({'error': 'Your session expired or data is missing.'}, status=400)

    try:
        form = OrderCreateForm(order_data)
        
        if form.is_valid():
            order = form.save(commit=False) 
            order.stripe_pid = stripe_pid
            order.paid = True 
            
            if request.user.is_authenticated:
                order.user = request.user
                
            order.save() 
            
            product_ids = cart_session.keys()
            products = ProductPage.objects.filter(id__in=product_ids)
            product_map = {str(p.id): p for p in products}

            for product_id, quantity in cart_session.items():
                product = product_map.get(product_id)
                if product and quantity > 0:
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        price=product.price,
                        quantity=quantity
                    )
            
            if 'cart' in request.session:
                del request.session['cart']
            if 'order_data' in request.session:
                del request.session['order_data']
            request.session.modified = True

            # Save order_id to session *just* for the thank you page
            request.session['last_order_id'] = order.id

            return JsonResponse({'success': True, 'redirect_url': reverse('checkout_done')})
        else:
            return JsonResponse({'error': 'Invalid address data.'}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def checkout_done_page(request):
    """
    Displays the final "Thank You" page.
    """
    # Get the order ID we just saved, then clear it
    last_order_id = request.session.pop('last_order_id', None)
    
    if last_order_id:
        try:
            order = Order.objects.get(id=last_order_id)
            return render(request, 'home/checkout_done.html', {'order': order})
        except Order.DoesNotExist:
            pass # Fallback to generic page

    # Show a generic thank you if session/order fails
    return render(request, 'home/checkout_done.html')


# --- NEW AUTHENTICATION VIEWS ---

def login_view(request):
    """
    Handles the login form submission from the popup.
    """
    referer = request.META.get('HTTP_REFERER', '/') 
    
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(referer)
        else:
            messages.error(request, "Invalid username or password. Please try again.")
            return redirect(referer)
    
    return redirect(referer)


def logout_view(request):
    """
    Logs the user out.
    """
    referer = request.META.get('HTTP_REFERER', '/')
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect(referer)