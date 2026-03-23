from django.contrib import admin

from .models import LeadCapture, Reservation, Submission


admin.site.site_header = "Meditation Landing Admin"
admin.site.site_title = "Meditation Landing Admin"
admin.site.index_title = "Site administration"


@admin.register(LeadCapture)
class LeadCaptureAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "country", "phone", "created_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("country", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    list_per_page = 25

    fieldsets = (
        ("Contact details", {"fields": ("name", "email", "country", "phone")}),
        ("Metadata", {"fields": ("created_at",)}),
    )


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("get_session_date_label", "get_session_type_label", "created_at")
    list_filter = ("session_type", "session_date", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    list_per_page = 25

    fieldsets = (
        ("Reservation details", {"fields": ("session_date", "session_type")}),
        ("Metadata", {"fields": ("created_at",)}),
    )

    @admin.display(description="Session date", ordering="session_date")
    def get_session_date_label(self, obj):
        return obj.get_session_date_display()

    @admin.display(description="Session type", ordering="session_type")
    def get_session_type_label(self, obj):
        return obj.get_session_type_display()


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "get_session_type_label", "get_session_date_label", "created_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("session_type", "session_date", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    list_per_page = 25

    fieldsets = (
        ("Contact details", {"fields": ("name", "email", "phone")}),
        ("Reservation details", {"fields": ("session_type", "session_date", "message")}),
        ("Metadata", {"fields": ("created_at",)}),
    )

    @admin.display(description="Session date", ordering="session_date")
    def get_session_date_label(self, obj):
        return obj.get_session_date_display()

    @admin.display(description="Session type", ordering="session_type")
    def get_session_type_label(self, obj):
        return obj.get_session_type_display() if obj.session_type else "Not provided"
