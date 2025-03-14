from django import forms
from song_signup.models import SongRequest, validate_partners_changed, Singer
from django.core.exceptions import ValidationError

class FileUploadForm(forms.Form):
    file = forms.FileField()

class TickchakUploadForm(forms.Form):
    file = forms.FileField()
    event_sku = forms.CharField(label="Event SKU")
    event_date = forms.CharField(label="Event date (e.g 15.3.25)")
    generate_cheat_code = forms.BooleanField(required=False)

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
