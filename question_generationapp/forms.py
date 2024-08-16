# question_generationapp/forms.py
from django import forms
from .models import *
from django.forms import DateInput
from django.forms.fields import DateField
from django.forms.widgets import PasswordInput
from django import forms
from django.forms import DateInput, DateField, PasswordInput
from django import forms


   
class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
    }))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Confirm Password',
        'class': 'form-control',
    }))

    class Meta:
        model = Account
        fields = ['first_name', 'last_name', 'phone_number', 'email', 'password', ]

    def clean(self):
        cleaned_data = super(RegistrationForm, self).clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

    def save(self, commit=True):
        user = super(RegistrationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class TextForm(forms.Form):
    text = forms.CharField(
        label='Enter Text',
        widget=forms.Textarea(attrs={'placeholder': 'Enter your text here', 'rows': 4, 'cols': 40}),
        max_length=1000,  
        help_text='Maximum 1000 characters'  
    )

class TextContentForm(forms.Form):
    text_content = forms.CharField(widget=forms.Textarea, label='Text Content')
