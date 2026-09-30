from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
admin.site.register(User, UserAdmin)


from .models import ContactEnquiry
@admin.register(ContactEnquiry)
class ContactEnquiryAdmin(admin.ModelAdmin):
    list_display = ['name', 'organisation', 'interest', 'created_at', 'handled']
    list_filter = ['interest', 'handled', 'created_at']
    search_fields = ['name', 'email', 'organisation', 'message']
    readonly_fields = ['reference', 'created_at', 'consent']
