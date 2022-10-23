from django.contrib import admin
from .models import Operation, Bundle
from gnosis.eth.django.admin import BinarySearchAdmin


class OperationsAdmin(BinarySearchAdmin):
    list_display = (['sender', 'nonce', 'status'])

admin.site.register(Operation, OperationsAdmin)
admin.site.register(Bundle)

