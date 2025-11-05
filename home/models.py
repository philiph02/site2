from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel


from django.db import models

# Hauptseite (Root)

ORIENTATION_CHOICES = [
    ('horizontal', 'Horizontal'),
    ('vertical', 'Vertical'),
    ('squared', 'Squared'),
    ('other', 'Other'),
]


class HomePage(Page):
    template = "home/index.html"


    def get_context(self, request):
        context = super().get_context(request)
        
        context['index_shop_page'] = self.get_children().type(IndexShopPage).live().first()
        context['videography_page'] = self.get_children().type(VideographyPage).live().first()
        context['photography_page'] = self.get_children().type(PhotographyPage).live().first()
        return context

# Erste Ebene unter Home (alle 3!)
class IndexShopPage(Page):
    template = "home/index_shop.html"

    def get_context(self, request):
        context = super().get_context(request)
        context['index_page'] = HomePage.objects.live().first()
        
        # HIER DIE ZEILE HINZUFÜGEN:
        if context['index_page']:
            context['photography_page'] = context['index_page'].get_children().type(PhotographyPage).live().first()

        context['products'] = self.get_children().type(ProductPage).live()
        context['registration_page'] = self.get_children().type(RegistrationPage).live().first()
        context['shop_page'] = self.get_children().type(ShopPage).live().first()
        context['about_page'] = self.get_children().type(AboutPage).live().first()
        context['blog_page'] = self.get_children().type(BlogPage).live().first()
        context['faq_page'] = self.get_children().type(FaqPage).live().first()
        context['contact_page'] = self.get_children().type(ContactPage).live().first()

        products_specific = self.get_children().type(ProductPage).live().specific()
        horizontal = [p for p in products_specific if p.orientation == 'horizontal'][:7]
        vertical   = [p for p in products_specific if p.orientation == 'vertical'][:7]
        squared    = [p for p in products_specific if p.orientation == 'squared'][:7]

        # Pad each to exactly 7 items
        def pad(lst, size):
            return lst + [None] * (size - len(lst))

        horizontal = pad(horizontal, 7)
        vertical = pad(vertical, 7)
        squared = pad(squared, 7)

        # Flatten row-wise for Swiper: horizontals, then verticals, then squareds
        grid_products = horizontal + vertical + squared
        context['grid_products'] = grid_products


        return context

    
    def get_products(self):
        return self.get_children().live().specific()


    

class VideographyPage(Page):
    template = "home/videography.html"
    description = RichTextField(blank=True)
    content_panels = Page.content_panels + [FieldPanel('description')]

class PhotographyPage(Page):
    template = "home/photography.html"
    description = RichTextField(blank=True)
    content_panels = Page.content_panels + [FieldPanel('description')]

# Unterseiten von IndexShop

class ProductPage(Page):
    parent_page_types = ['home.IndexShopPage']
    template = "home/details.html"
    description = RichTextField(blank=True)
    description_text = models.TextField(
        blank=True,  # Macht das Feld optional
        help_text="Einfacher Text für eine zusätzliche Beschreibung." # Optionaler Hilfetext
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
        FieldPanel('product_image'),  
        FieldPanel('orientation'),
    ]

    # VVV ALLES AB HIER WURDE KORREKT EINGERÜCKT VVV
    
    def get_context(self, request, *args, **kwargs):
            """
            Holt 3 zufällige, veröffentlichte Produkte, die nicht das aktuelle sind.
            """
            # Holt den Standard-Kontext
            context = super().get_context(request, *args, **kwargs)

            # Baue die Query:
            related_products = ProductPage.objects.live().exclude(pk=self.pk).order_by('?')[:3]

            # Füge das Ergebnis dem Kontext hinzu
            context['related_products'] = related_products

            return context

class RegistrationPage(Page):
    template = "home/registration.html"

class ShopPage(Page):
    template = "home/shop.html"

class AboutPage(Page):
    template = "home/about.html"

class BlogPage(Page):
    template = "home/blog.html"

class FaqPage(Page):
    template = "home/faq.html"

class ContactPage(Page):
    template = "home/contact.html"