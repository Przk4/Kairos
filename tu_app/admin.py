from django.contrib import admin
from .models import CanvasToken, Course, Module, ModuleItem

# Register your models here.

@admin.register(CanvasToken)
class CanvasTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'canvas_user_id', 'is_expired', 'updated_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__username', 'canvas_user_id')
    readonly_fields = ('canvas_user_id', 'created_at', 'updated_at')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'user', 'canvas_course_id', 'enrollment_role')
    list_filter = ('enrollment_role', 'updated_at')
    search_fields = ('name', 'code', 'canvas_course_id')
    readonly_fields = ('canvas_course_id', 'created_at', 'updated_at')


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'position', 'is_locked', 'updated_at')
    list_filter = ('course', 'is_locked', 'position')
    search_fields = ('name', 'canvas_module_id')
    readonly_fields = ('canvas_module_id', 'created_at', 'updated_at')


@admin.register(ModuleItem)
class ModuleItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'item_type', 'module', 'position', 'is_locked')
    list_filter = ('item_type', 'is_locked', 'module__course')
    search_fields = ('title', 'canvas_item_id')
    readonly_fields = ('canvas_item_id', 'created_at')
