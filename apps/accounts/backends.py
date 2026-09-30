from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        User = get_user_model()
        if '@' not in username:
            return super().authenticate(request, username=username, password=password, **kwargs)
        users = list(User.objects.filter(email__iexact=username.strip())[:2])
        if len(users) == 1:
            user = users[0]
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        else:
            User().set_password(password)
        return None
