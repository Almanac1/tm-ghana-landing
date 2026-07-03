from django.contrib import admin

from .models import BlogArticle, ClassDate, HomePageContent, LeadCapture, Reservation, Submission


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


@admin.register(ClassDate)
class ClassDateAdmin(admin.ModelAdmin):
    list_display = ("date", "time", "session_type", "is_active", "display_order")
    list_editable = ("is_active", "display_order")
    list_filter = ("session_type", "is_active", "date")
    ordering = ("display_order", "date", "time")
    list_per_page = 25

    fieldsets = (
        ("Class details", {"fields": ("session_type", "date", "time")}),
        ("Display", {"fields": ("is_active", "display_order")}),
    )


@admin.register(BlogArticle)
class BlogArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_published", "created_at", "updated_at")
    list_filter = ("is_published", "created_at", "updated_at")
    search_fields = ("title", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    list_per_page = 25

    fieldsets = (
        ("Article", {"fields": ("title", "slug", "excerpt", "body")}),
        ("Publishing", {"fields": ("is_published",)}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(HomePageContent)
class HomePageContentAdmin(admin.ModelAdmin):
    list_display = ("hero_headline", "cta_button_text", "is_active", "updated_at")
    list_filter = ("is_active", "updated_at")
    readonly_fields = ("updated_at",)
    ordering = ("-updated_at",)
    list_per_page = 10

    fieldsets = (
        ("Hero", {"fields": ("hero_headline", "hero_subtitle", "hero_youtube_url")}),
        ("CTA", {"fields": ("cta_button_text", "cta_button_link")}),
        ("Status", {"fields": ("is_active", "updated_at")}),
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
        return obj.session_date

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
        return obj.session_date

    @admin.display(description="Session type", ordering="session_type")
    def get_session_type_label(self, obj):
        return obj.get_session_type_display() if obj.session_type else "Not provided"
