# home/views.py
from django.shortcuts import redirect
from django.http import HttpResponseBadRequest
from .models import ProductPage  # Um das Produkt in der DB zu finden

def add_to_cart(request, product_id):
    """
    Fügt ein Produkt zur Session hinzu oder erhöht die Menge.
    """
    # 1. Finde das Produkt
    try:
        product = ProductPage.objects.get(id=product_id)
    except ProductPage.DoesNotExist:
        return HttpResponseBadRequest("Produkt nicht gefunden")

    # 2. Hole den Warenkorb aus der Session (oder erstelle einen leeren)
    #    Wir speichern 'cart' als Dictionary: { 'produkt_id': menge, ... }
    cart = request.session.get('cart', {})
    
    # 3. Hole die Menge aus dem Formular (siehe Schritt 3)
    #    Wir benutzen .get() mit einem Standardwert von 1
    try:
        quantity = int(request.POST.get('quantity', 1))
    except ValueError:
        quantity = 1

    # 4. Produkt zum Warenkorb hinzufügen oder Menge aktualisieren
    product_id_str = str(product.id) # Session-Keys müssen Strings sein
    
    if product_id_str in cart:
        cart[product_id_str] += quantity
    else:
        cart[product_id_str] = quantity

    # 5. Speichere den geänderten Warenkorb zurück in die Session
    request.session['cart'] = cart
    request.session.modified = True  # Django mitteilen, dass wir was geändert haben

    # 6. Leite den Benutzer zurück zur Shop-Hauptseite (oder dorthin, wo er herkam)
    #    Besser wäre: redirect(request.META.get('HTTP_REFERER', '/'))
    return redirect(request.META.get('HTTP_REFERER', '/'))

# HINZUFÜGEN: Diese neue Funktion
def remove_one_from_cart(request, product_id):
    """
    Verringert die Menge eines Artikels im Warenkorb um 1.
    """
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)

    if product_id_str in cart:
        # Menge um 1 verringern
        cart[product_id_str] -= 1
        
        # Wenn Menge 0 oder weniger ist, Artikel ganz entfernen
        if cart[product_id_str] <= 0:
            del cart[product_id_str]
    
    request.session['cart'] = cart
    request.session.modified = True
    
    # Zurück zur Seite, von der man kam
    return redirect(request.META.get('HTTP_REFERER', '/'))

def add_to_cart(request, product_id):
    """
    Fügt ein Produkt zur Session hinzu.
    Nimmt Menge 1 (für GET-Requests) oder die Menge aus dem Formular (für POST).
    """
    try:
        product = ProductPage.objects.get(id=product_id)
    except ProductPage.DoesNotExist:
        return HttpResponseBadRequest("Produkt nicht gefunden")

    cart = request.session.get('cart', {})
    quantity = 1  # Standard-Menge ist 1

    if request.method == 'POST':
        # Wenn ein Formular gesendet wurde, versuche die Menge auszulesen
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            quantity = 1  # Zurück auf 1, falls ungültige Daten gesendet wurden
    
    # Wenn es ein GET-Request ist (Klick auf index_shop), bleibt die Menge einfach 1

    product_id_str = str(product.id)
    
    if product_id_str in cart:
        cart[product_id_str] += quantity
    else:
        cart[product_id_str] = quantity

    request.session['cart'] = cart
    request.session.modified = True
    
    # Zurück zur Seite, von der man kam
    return redirect(request.META.get('HTTP_REFERER', '/'))