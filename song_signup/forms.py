from django import forms
from song_signup.models import SongRequest, validate_partners_changed, Singer
from django.core.exceptions import ValidationError

class FileUploadForm(forms.Form):
    file = forms.FileField()

class TickchakUploadForm(forms.Form):
    file = forms.FileField()
    event_name = forms.CharField()
    event_sku = forms.CharField()

class SongRequestForm(forms.ModelForm):
    class Meta:
        model = SongRequest
        fields = '__all__'

    def clean_partners(self):
        partners = self.cleaned_data.get('partners', [])
        singer = self.cleaned_data['singer']
        if partners:
            if singer in partners:
                raise ValidationError("A singer cannot add himself/herself as a partner")

            validate_partners_changed(
                sender=SongRequest.partners.through,
                instance=self.instance,
                action="pre_add",
                reverse=False,
                model=Singer,
                pk_set={x.pk for x in partners}
          )
        return partners
