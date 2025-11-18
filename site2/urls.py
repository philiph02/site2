from django.conf import settings
from django.urls import include, path
from django.contrib import admin

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

from search import views as search_views
from home import views as home_views 

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("search/", search_views.search, name="search"),
    
    # Cart URLs
    # 'add' still uses int because we add by the Product Page ID
    path("cart/add/<int:product_id>/", home_views.add_to_cart, name="add_to_cart"),
    
    # CHANGE HERE: Changed <int:product_id> to <str:product_id>
    # This allows keys like "16_2_False" to be passed correctly.
    path("cart/remove_one/<str:product_id>/", home_views.remove_one_from_cart, name="remove_one_from_cart"),

    # Checkout URLs
    path("checkout/", home_views.checkout_page, name="checkout"),
    path("checkout/success/", home_views.checkout_success, name="checkout_success"),
    path("checkout/done/", home_views.checkout_done_page, name="checkout_done"),

    # NEW Authentication URLs
    path("login/", home_views.login_view, name="login_view"),
    path("logout/", home_views.logout_view, name="logout_view"),

    path("api/calculate-shipping/", home_views.calculate_shipping_cost, name="calculate_shipping_cost"),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns = urlpatterns + [
    # Wagtail's page serving mechanism must be LAST
    path("", include(wagtail_urls)),
]