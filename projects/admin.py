from django.contrib import admin
from .models import Project, Part, PurchasedPart, ProjectImage, Designer, Group, Material, Instructions

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'designer', 'created_at', 'updated_at', 'get_total_parts')
    list_filter = ('user', 'designer', 'created_at')
    search_fields = ('name', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'user', 'designer')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_total_parts(self, obj):
        return obj.total_parts
    get_total_parts.short_description = 'Total Parts'

@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'quantity', 'material', 'color', 'completed', 'group', 'volume')
    list_filter = ('project', 'material', 'color', 'group', 'completed')
    search_fields = ('name', 'material', 'color')
    readonly_fields = ('volume',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'project', 'quantity', 'group')
        }),
        ('Details', {
            'fields': ('material', 'color', 'completed')
        }),
        ('Files', {
            'fields': ('stl_file', 'thumbnail')
        }),
        ('Calculated Fields', {
            'fields': ('volume',),
            'classes': ('collapse',)
        }),
    )

@admin.register(Designer)
class DesignerAdmin(admin.ModelAdmin):
    list_display = ('name', 'mmf_url', 'patreon_url', 'cults3d_url', 'website_url')
    search_fields = ('name',)
    list_filter = ('name',)

@admin.register(PurchasedPart)
class PurchasedPartAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'price', 'quantity', 'status', 'link')
    list_filter = ('project', 'status')
    search_fields = ('name', 'link')

@admin.register(ProjectImage)
class ProjectImageAdmin(admin.ModelAdmin):
    list_display = ('project', 'uploaded_at')
    list_filter = ('project', 'uploaded_at')
    date_hierarchy = 'uploaded_at'

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'density', 'cost', 'weight', 'get_cost_per_kg', 'get_total_used', 'is_active')
    list_filter = ('is_active', 'brand')
    search_fields = ('name', 'brand', 'description')
    readonly_fields = ('get_cost_per_kg', 'get_total_used')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'brand', 'link', 'is_active')
        }),
        ('Physical Properties', {
            'fields': ('density', 'color')
        }),
        ('Cost Information', {
            'fields': ('cost', 'weight', 'get_cost_per_kg')
        }),
        ('Usage Statistics', {
            'fields': ('get_total_used',),
            'classes': ('collapse',)
        }),
    )

    def get_cost_per_kg(self, obj):
        return obj.cost_per_kg
    get_cost_per_kg.short_description = 'Cost per kg'

    def get_total_used(self, obj):
        return f"{obj.total_used:.2f} g"
    get_total_used.short_description = 'Total Used'

@admin.register(Instructions)
class InstructionsAdmin(admin.ModelAdmin):
    list_display = ('project', 'order', 'description', 'created_at')
    list_filter = ('project',)
    search_fields = ('description', 'project__name')
    ordering = ('project', 'order')
