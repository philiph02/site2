from django.db import models
from django.shortcuts import render, redirect  # <-- ADD RENDER & REDIRECT
from django.contrib.auth import login         # <-- ADD LOGIN
from django.contrib import messages         # <-- ADD MESSAGES
from django.contrib.auth.models import User     # <-- ADD USER

from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel

# Import the new form
      # <-- ADD FORM IMPORT

# --- 1. "About Me" Seite ---
class HomePage(Page):
    template = "home/index.html" # Your models.py had index.html
    # This page is now "About Me"

# --- 2. "Photography" Seite ---
class PhotographyPage(Page):
    template = "home/photography.html"

# --- 3. "Shop" Hauptseite ---
class IndexShopPage(Page):
    template = "home/index_shop.html"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        all_products = ProductPage.objects.live().specific()
        
        horizontal = [p for p in all_products if p.orientation == 'horizontal'][:7]
        vertical   = [p for p in all_products if p.orientation == 'vertical'][:7]
        squared    = [p for p in all_products if p.orientation == 'squared'][:7]

        def pad(lst, size):
            return lst + [None] * (size - len(lst))

        horizontal = pad(horizontal, 7)
        vertical = pad(vertical, 7)
        squared = pad(squared, 7)

        grid_products = horizontal + vertical + squared
        context['grid_products'] = grid_products
        
        # Get the registration page
        context['registration_page'] = RegistrationPage.objects.live().first()

        return context

# --- Produkt-Detailseite ---
ORIENTATION_CHOICES = [
    ('horizontal', 'Horizontal'),
    ('vertical', 'Vertical'),
    ('squared', 'Squared'), 
    ('other', 'Other'),
]

class ProductPage(Page):
    parent_page_types = ['home.IndexShopPage'] 
    template = "home/details.html"
    
    description = RichTextField(blank=True)
    description_text = models.TextField(
        blank=True,
        help_text="Einfacher Text für eine zusätzliche Beschreibung."
    )
    price = models.DecimalField(
        max_digits=7, 
        decimal_places=2, 
        help_text="Price for the RAW A2 Print (e.g., 39.99)" # <-- Updated help text
    )

    frame_addon_price = models.DecimalField(
        max_digits=7, 
        decimal_places=2, 
        blank=True, 
        null=True, 
        help_text="ADD-ON price for the A2 Frame (e.g., 20.00). This will be added to the base price."
    )

    product_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    orientation = models.CharField(
        max_length=10,
        choices=ORIENTATION_CHOICES,
        default='horizontal'
    )
    
    content_panels = Page.content_panels + [
        FieldPanel('description'),
        FieldPanel('description_text'),
        FieldPanel('price'),
        FieldPanel('frame_addon_price'),  # <-- ADD THIS LINE
        FieldPanel('product_image'),
        FieldPanel('orientation'),
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        related_products = (
            ProductPage.objects.live()
            .exclude(pk=self.pk)
            .filter(orientation='vertical') 
            .order_by('?')[:3]
        )
        context['related_products'] = related_products
        return context

# --- Registrierungsseite (JETZT MIT LOGIK) ---
class RegistrationPage(Page):
    parent_page_types = ['home.IndexShopPage']
    template = "home/registration.html"

    # In class RegistrationPage(Page):

    def serve(self, request, *args, **kwargs):
        # This method handles both GET and POST requests for the page
        
        from .forms import RegistrationForm  # <-- PASTE THE LINE HERE
        
        # Get the parent shop page to redirect to
        shop_page = IndexShopPage.objects.live().first() # Get the shop page
        
        if request.method == 'POST':

            form = RegistrationForm(request.POST)
            if form.is_valid():
                # Create the new user
                user = form.save()
                # Log them in automatically
                login(request, user)
                messages.success(request, f"Welcome, {user.username}! You are now registered and logged in.")
                # Redirect to the main shop page
                if shop_page:
                    return redirect(shop_page.url)
                else:
                    return redirect('/')
            else:
                # Form is invalid, add error messages to be displayed
                messages.error(request, f"Please correct the errors below.")
        else:
            # GET request, show a blank form
            form = RegistrationForm()

        # Render the template
        context = self.get_context(request)
        context['form'] = form
        return render(request, self.template, context)


# --- 4. Models für den Checkout ---
# (Dieser Code von der Stripe-Integration bleibt unverändert)

class Order(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    address = models.CharField(max_length=250)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    paid = models.BooleanField(default=False)
    # NEW: Link order to a user (can be null for guest checkout)

    user = models.ForeignKey(
        User,  # <-- This should be the User model
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    # NEW: Store Stripe Payment Intent ID
    stripe_pid = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f'Order {self.id}'

    def get_total_cost(self):
        return sum(item.get_cost() for item in self.items.all())

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(ProductPage, related_name='order_items', on_delete=models.CASCADE) 
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return str(self.id)

    def get_cost(self):
        return self.price * self.quantity