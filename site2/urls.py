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
    
    path("cart/add/<int:product_id>/", home_views.add_to_cart, name="add_to_cart"),
    path("cart/remove_one/<str:product_id>/", home_views.remove_one_from_cart, name="remove_one_from_cart"),

    path("checkout/", home_views.checkout_page, name="checkout"),
    
    path("checkout/calculate-shipping/", home_views.calculate_shipping_options, name="calculate_shipping_options"),

    path("checkout/success/", home_views.checkout_success, name="checkout_success"),

    path("login/", home_views.login_view, name="login_view"),
    path("logout/", home_views.logout_view, name="logout_view"),
]

if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns = urlpatterns + [
    path("", include(wagtail_urls)),
]