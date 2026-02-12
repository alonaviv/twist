from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Round


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('round_number', 'url', 'password', 'has_link', 'clear_button')
    list_editable = ('url', 'password')
    ordering = ('round_number',)
    change_list_template = 'admin/pub_quiz/round/change_list.html'

    def get_queryset(self, request):
        # Ensure all 6 round slots exist so the admin always has 6 places to edit
        for i in range(1, 7):
            Round.objects.get_or_create(round_number=i, defaults={'url': ''})
        return super().get_queryset(request)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('clear/<int:pk>/', self.admin_site.admin_view(self.clear_round_view), name='pub_quiz_round_clear'),
            path('clear-all/', self.admin_site.admin_view(self.clear_all_view), name='pub_quiz_round_clear_all'),
        ]
        return custom + urls

    def clear_round_view(self, request, pk):
        obj = Round.objects.get(pk=pk)
        obj.url = ''
        obj.password = ''
        obj.save(update_fields=['url', 'password'])
        messages.success(request, f'Cleared URL and password for Round {obj.round_number}.')
        return HttpResponseRedirect(reverse('admin:pub_quiz_round_changelist'))

    def clear_all_view(self, request):
        updated = Round.objects.all().update(url='', password='')
        messages.success(request, f'Cleared all URLs and passwords for {updated} rounds.')
        return HttpResponseRedirect(reverse('admin:pub_quiz_round_changelist'))

    def clear_button(self, obj):
        if not obj.url:
            return ''
        url = reverse('admin:pub_quiz_round_clear', args=[obj.pk])
        return format_html('<a href="{}" class="button">Clear</a>', url)
    clear_button.short_description = 'Clear URL'

    def has_delete_permission(self, request, obj=None):
        return False  # Keep exactly 6 round slots

    def has_link(self, obj):
        return bool(obj.url and obj.password)
    has_link.boolean = True
    has_link.short_description = 'Link set'
