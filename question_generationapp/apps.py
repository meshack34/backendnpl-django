# question_generationapp/apps.py
from django.apps import AppConfig

class QuestionGenerationAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'question_generationapp'

    def ready(self):
        import question_generationapp.signals
