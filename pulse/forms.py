from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Monitor
from .services import UnsafeURL, validate_public_url


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Letters, numbers and @ . + - _ only."
        self.fields["email"].help_text = "We send down-alerts here."
        self.fields["password1"].help_text = "At least 8 characters, not too common."
        self.fields["password2"].help_text = ""


class MonitorForm(forms.ModelForm):
    class Meta:
        model = Monitor
        fields = ("name", "url", "interval_seconds", "is_public")
        labels = {"interval_seconds": "Check every (seconds)", "is_public": "Show on the public status board"}

    def clean_url(self):
        url = self.cleaned_data["url"]
        try:
            validate_public_url(url)
        except UnsafeURL as exc:
            raise forms.ValidationError(str(exc))
        return url
