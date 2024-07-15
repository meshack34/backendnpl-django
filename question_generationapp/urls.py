from django.urls import path
from .views import RegisterView, LoginView, UserDetailView, QuestionGenerationView

urlpatterns = [
    path('api/register/', RegisterView.as_view(), name='register'),
    path('api/login/', LoginView.as_view(), name='login'),
    path('api/user-detail/', UserDetailView.as_view(), name='user-detail'),
    path('api/generate-questions/', QuestionGenerationView.as_view(), name='generate-questions'),
]

