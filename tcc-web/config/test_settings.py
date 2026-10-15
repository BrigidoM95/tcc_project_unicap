from .settings import *
CACHES = {'default': {'BACKEND':'django.core.cache.backends.locmem.LocMemCache'}}
STORAGES = {'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
 'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
