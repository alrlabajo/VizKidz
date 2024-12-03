from django import forms
from .models import UserCredentials

class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = UserCredentials
        fields = ('username', 'email', 'password')

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

class FileUploadForm(forms.Form):
    file = forms.FileField(label="")

class ChartTypeForm(forms.Form):
    CHART_CHOICES = [
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('time', 'Time Series Chart'),
        ('pie', 'Pie Chart'),
        ('doughnut', 'Doughnut Chart'),
    ]
    chart_type = forms.ChoiceField(choices=CHART_CHOICES, label="Select Chart Type")

