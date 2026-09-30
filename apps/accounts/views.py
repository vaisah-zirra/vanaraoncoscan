from django.contrib.auth.views import LoginView
from django.contrib.auth.forms import AuthenticationForm

class ReturningLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Email address or username'
        self.fields['username'].widget.attrs['autocomplete'] = 'username'

class DemoLoginView(LoginView):
    authentication_form = ReturningLoginForm
    template_name = 'registration/login.html'
