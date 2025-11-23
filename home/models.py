from django.db import models
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.models import User

from wagtail.models import Page, Orderable
from wagtail.fields import RichTextField
from wagtail.snippets.models import register_snippet
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, InlinePanel, FieldRowPanel
from modelcluster.fields import ParentalKey
from wagtail.search import index

# --- 1. PRICING SNIPPET ---
@register_snippet
class PrintSizePrice(models.Model):
    size_name = models.CharField(max_length=100)
    base_price = models.DecimalField(decimal_places=2, max_digits=10)
    frame_addon_price = models.DecimalField(decimal_places=2, max_digits=10)

    panels = [
        FieldPanel('size_name'),
        FieldRowPanel([FieldPanel('base_price'), FieldPanel('frame_addon_price')])
    ]
    def __str__(self):
        return f"{self.size_name} ({self.base_price} €)"

# --- 2. PAGES ---
class HomePage(Page):
    template = "home/index.html"

class PhotographyPage(Page):
    template = "home/photography.html"

class ProductPage(Page):
    template = "home/details.html"
    
    product_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=False, on_delete=models.SET_NULL, related_name="+"
    )
    orientation = models.CharField(
        max_length=20, 
        choices=[('horizontal', 'Horizontal'), ('vertical', 'Vertical'), ('squared', 'Squared')],
        default='vertical'
    )
    description_text = models.TextField(blank=True)

    content_panels = Page.content_panels + [
        MultiFieldPanel([FieldPanel("product_image"), FieldPanel("orientation")], heading="Product Details"),
        FieldPanel("description_text"),
    ]

    parent_page_types = ['home.IndexShopPage']

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        # Random related products
        context['related_products'] = ProductPage.objects.live().exclude(pk=self.pk).order_by('?')[:3]
        context['all_variants'] = PrintSizePrice.objects.all().order_by('base_price')
        return context

# --- 3. SHOP INDEX (THE GRID LOGIC) ---
class FeaturedProduct(Orderable):
    page = ParentalKey('home.IndexShopPage', related_name='featured_products')
    product_to_link = models.ForeignKey('home.ProductPage', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    slider_image = models.ForeignKey("wagtailimages.Image", null=True, on_delete=models.SET_NULL, related_name="+")
    slider_title = RichTextField()
    slider_subtitle = models.CharField(max_length=255, blank=True)
    slider_description = models.TextField(blank=True)
    image_caption_title = models.CharField(max_length=100, blank=True)
    image_caption_subtitle = models.CharField(max_length=100, blank=True)

    panels = [
        FieldPanel('product_to_link'),
        FieldPanel('slider_image'),
        FieldPanel('slider_title'),
        FieldPanel('slider_subtitle'),
        FieldPanel('slider_description'),
        FieldPanel('image_caption_title'),
        FieldPanel('image_caption_subtitle'),
    ]

class IndexShopPage(Page):
    template = "home/index_shop.html"

    content_panels = Page.content_panels + [
        MultiFieldPanel([InlinePanel('featured_products', label="Slider Slides")], heading="Slider Content")
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        
        # --- GRID LOGIC: Fetch items in Admin Sort Order ---
        # This allows you to drag-and-drop items in Wagtail to rearrange them
        grid_products = ProductPage.objects.child_of(self).live().specific()
        context['grid_products'] = grid_products

        # Price Logic
        cheapest = PrintSizePrice.objects.all().order_by('base_price').first()
        context['cheapest_price'] = cheapest.base_price if cheapest else 0
        
        context['registration_page'] = RegistrationPage.objects.live().first()
        context['featured_slider_items'] = self.featured_products.all()
        return context

# --- 4. REGISTRATION ---
class RegistrationPage(Page):
    template = "home/registration.html"
    def serve(self, request, *args, **kwargs):
        from .forms import RegistrationForm
        shop_page = IndexShopPage.objects.live().first()
        
        if request.method == 'POST':
            form = RegistrationForm(request.POST)
            if form.is_valid():
                user = form.save()
                login(request, user)
                messages.success(request, f"Welcome, {user.username}!")
                return redirect(shop_page.url if shop_page else '/')
            else:
                messages.error(request, "Please correct the errors below.")
        else:
            form = RegistrationForm()
        
        context = self.get_context(request)
        context['form'] = form
        return render(request, self.template, context)


# --- 5. CHECKOUT MODELS (REQUIRED FOR VIEWS.PY) ---

class Order(models.Model):
    country = models.CharField(max_length=100, default='Austria')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    address = models.CharField(max_length=250)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)
    paid = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    stripe_pid = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f'Order {self.id}'

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(ProductPage, related_name='order_items', on_delete=models.CASCADE) 
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    size_name = models.CharField(max_length=100, blank=True, default='')
    framed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.order.id} - {self.product.title}"