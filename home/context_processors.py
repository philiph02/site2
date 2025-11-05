from .models import IndexShopPage, ProductPage, HomePage, PhotographyPage

def cart_context(request):
    """
    Stellt den Warenkorb-Kontext (items, total, count) auf JEDER Seite bereit.
    """
    cart = request.session.get('cart', {})
    cart_items = []
    cart_total_price = 0
    cart_total_count = 0

    product_ids = cart.keys()
    products = ProductPage.objects.filter(id__in=product_ids)
    product_map = {str(product.id): product for product in products}

    for product_id, item_data in cart.items():
        product = product_map.get(product_id)
        if product:
            
            # --- KORREKTUR START ---
            # Prüfen, ob item_data ein dict oder nur ein int ist
            if isinstance(item_data, dict):
                quantity = item_data.get('quantity', 0)
            elif isinstance(item_data, int):
                quantity = item_data  # Die Daten sind direkt die Menge
            else:
                quantity = 0 # Fallback, falls die Daten ungültig sind
            # --- KORREKTUR ENDE ---

            item_total = product.price * quantity
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'item_total': item_total,
            })
            cart_total_price += item_total
            cart_total_count += quantity

    return {
        'cart_items': cart_items,
        'cart_total_price': cart_total_price,
        'cart_total_count': cart_total_count,
    }


def global_nav_links(request):
    """
    Stellt die Haupt-Navigationslinks (About, Shop, Photography) auf JEDER Seite bereit.
    """
    return {
        'about_page': HomePage.objects.live().first(),
        'shop_page': IndexShopPage.objects.live().first(),
        'photography_page': PhotographyPage.objects.live().first(),
    }