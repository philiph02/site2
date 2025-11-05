from django.db import models
import random
from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel
# KEIN ImageChooserPanel-Import mehr nötig

# --- 1. "About Me" Seite ---
# Verwendet home/index.html
class HomePage(Page):
    template = "home/index.html"
    # Diese Seite ist jetzt "About Me"

# --- 2. "Photography" Seite ---
# Verwendet home/photography_page.html
class PhotographyPage(Page):
    template = "home/photography.html"

# --- 3. "Shop" Hauptseite ---
# Verwendet home/index_shop.html
class IndexShopPage(Page):
    template = "home/index_shop.html"

    def get_context(self, request, *args, **kwargs):
        """
        Diese Funktion lädt NUR die Produkte für den Slider.
        Die Navigationslinks (shop_page, about_page etc.) kommen
        jetzt korrekt vom 'global_nav_links' context_processor.
        """
        context = super().get_context(request, *args, **kwargs)
        
        all_products = ProductPage.objects.live().specific()
        
        # Logik für den Slider (7 von jedem Typ, mit None aufgefüllt)
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
        
        # Holt die Registrierungsseite (falls sie im Login-Popup verlinkt ist)
        context['registration_page'] = self.get_children().type(RegistrationPage).live().first()

        return context

# --- Produkt-Detailseite ---
ORIENTATION_CHOICES = [
    ('horizontal', 'Horizontal'),
    ('vertical', 'Vertical'),
    ('squared', 'Squared'), 
    ('other', 'Other'),
]

class ProductPage(Page):
    # Ein Produkt kann NUR unter der IndexShopPage erstellt werden.
    parent_page_types = ['home.IndexShopPage'] 
    template = "home/details.html"
    
    description = RichTextField(blank=True)
    description_text = models.TextField(
        blank=True,
        help_text="Einfacher Text für eine zusätzliche Beschreibung."
    )
    price = models.DecimalField(max_digits=7, decimal_places=2)
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
        # HIER IST DIE KORREKTUR:
        FieldPanel('product_image'),  # Ersetzt den defekten ImageChooserPanel
        FieldPanel('orientation'),
    ]

    def get_context(self, request, *args, **kwargs):
        # Zeigt "related products" auf der Detailseite an
        context = super().get_context(request, *args, **kwargs)
        
        related_products = (
            ProductPage.objects.live()
            .exclude(pk=self.pk)
            .filter(orientation='vertical') 
            .order_by('?')[:3]
        )
        context['related_products'] = related_products
        return context

# --- Registrierungsseite ---
# Wir behalten nur die Registrierungsseite (die im Shop-Popup verwendet wird)
class RegistrationPage(Page):
    parent_page_types = ['home.IndexShopPage']
    template = "home/registration.html"