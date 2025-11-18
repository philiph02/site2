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


def payment_page(request):
    """
    Handles the Stripe Payment (Step 2 of checkout).
    (Updated to read new cart structure)
    """
    cart_session = request.session.get('cart', {})
    order_data = request.session.get('order_data')

    if not cart_session or not order_data:
        messages.error(request, "Your session has expired. Please start again.")
        return redirect(reverse('checkout'))

    # === NEUE LOGIK (FIX FÜR KASSENPREIS) ===
    total_price = Decimal(0)
    for cart_key, item_details in cart_session.items():
        try:
            price_per_item = Decimal(item_details['price'])
            quantity = int(item_details['quantity'])
            total_price += price_per_item * quantity
        except (InvalidOperation, TypeError, KeyError):
            # Skip malformed cart item
            continue

    total_price_cents = int(total_price * 100)
    
    # If total is 0, something is wrong (or cart empty)
    if total_price_cents <= 0:
        messages.error(request, "Your cart is empty or has an invalid price.")
        return redirect(reverse('checkout'))

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
    (Updated to save the new OrderItem fields)
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
            
            # === NEUE LOGIK (FIX FÜR ORDER CREATION) ===
            for cart_key, item_details in cart_session.items():
                try:
                    product = ProductPage.objects.get(id=item_details['product_id'])
                    
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        price=Decimal(item_details['price']),
                        quantity=int(item_details['quantity']),
                        # Save the new fields
                        size_name=item_details.get('size_name', ''),
                        framed=item_details.get('framed', False)
                    )
                except (ProductPage.DoesNotExist, TypeError, KeyError, InvalidOperation):
                    # Log this error, but don't stop the whole order
                    print(f"Error creating order item for cart_key {cart_key}")
                    continue
            
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