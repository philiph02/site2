from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-tpry$pktfah2vf*)rfq226t^5bn+gh%9$wj^c#c4$r(h66l462"

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


try:
    from .local import *
except ImportError:
    pass


# In site2/settings/dev.py
# ... (am Ende der Datei) ...

# ==================================
# STRIPE EINSTELLUNGEN (TEST-MODUS)
# ==================================
# Ersetze diese durch deine ECHTEN Test-Keys aus dem Stripe Dashboard
STRIPE_PUBLISHABLE_KEY = 'pk_test_51SRXm1K1a7JpQ4GHNG6Yz3HkLgFIBrwfVM2Z48I3SlIUxoprGrWWQNCZ967RVpzTvlsVVY8Bps7JfmR6Tb2Vuhtn009CGz1DHI'
STRIPE_SECRET_KEY = 'sk_test_51SRXm1K1a7JpQ4GHwv4fpUXP0ztFqyhSHjbnEkyH40hfiFOy98oJqeENdohFINzohWi723paRGV5pFhvEmnOhTjB00v4IGSPyR'