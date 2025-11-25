from .base import *
import os
import dj_database_url

# Security configuration
DEBUG = False
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-if-seen")

# ALLOWED_HOSTS: Allow Heroku app URL
# This allows any herokuapp.com subdomain. You can replace '*' with your specific app name later.
ALLOWED_HOSTS = ["*"] 

# Database configuration
# Parses the DATABASE_URL environment variable set by Heroku
DATABASES = {
    "default": dj_database_url.config(conn_max_age=600, ssl_require=True)
}

# Static Files (CSS/JS)
# Use Whitenoise to serve static files in production
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Security settings (Recommended for HTTPS)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

try:
    from .local import *
except ImportError:
    pass