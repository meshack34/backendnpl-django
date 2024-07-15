remember our backend data example :
{
    "text": "Cattle (Bos taurus) are large, domesticated, bovid ungulates widely kept as livestock. They are prominent modern members of the subfamily Bovinae and the most widespread species of the genus Bos. Mature female cattle are called cows and mature male cattle are bulls. Young female cattle are called heifers, young male cattle are oxen or bullocks, and castrated male cattle are known as steers.Cattle are commonly raised for meat, for dairy products, and for leather. As draft animals, they pull carts and farm implements. In India, cattle are sacred animals within Hinduism, and may not be killed. Small breeds such as the miniature Zebu are kept as pets",
    "use_evaluator": true,
    "num_questions": 5,
    "answer_style": "multiple_choice"
}


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_profile')
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]
    city = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    blood_group = models.CharField(max_length=3, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    age_years = models.PositiveIntegerField(null=True, blank=True)
    
    def __str__(self):
        return f'{self.user.first_name} {self.user.last_name}'

class GeneratedQuestions(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    entered_text = models.TextField()
    generated_questions = models.JSONField()  # Assuming you're storing the generated questions as JSON

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Generated Questions for {self.user.username} at {self.created_at}"

# Signals
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    instance.user_profile.save()



class QuestionGenerationView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = QuestionGenerationSerializer(data=request.data)
        if serializer.is_valid():
            text = serializer.validated_data['text']
            use_evaluator = serializer.validated_data['use_evaluator']
            num_questions = serializer.validated_data.get('num_questions', 10)
            answer_style = serializer.validated_data['answer_style']
            question_type = request.data.get('question_type', '')

            question_generator = QuestionGenerator()
            qa_list = question_generator.generate(
                article=text,
                num_questions=num_questions,
                answer_style=answer_style,
                use_evaluator=use_evaluator
            )

            simple_answer_questions = []
            multiple_choice_questions = []

            for qa in qa_list:
                if 'answer' in qa:
                    if isinstance(qa['answer'], list):
                        multiple_choice_questions.append(qa)
                    else:
                        simple_answer_questions.append(qa)

            if question_type == 'with_answers':
                questions = simple_answer_questions
            else:
                questions = multiple_choice_questions

            generated_questions_data = {
                'user': request.user.id,
                'entered_text': text,
                'generated_questions': qa_list
            }
            generated_questions_serializer = GeneratedQuestionsSerializer(data=generated_questions_data)
            if generated_questions_serializer.is_valid():
                generated_questions_serializer.save()

            return Response({
                'questions': questions,
                'question_type': question_type,
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    path('api/generate-questions/', QuestionGenerationView.as_view(), name='generate-questions'),




class QuestionGenerationSerializer(serializers.Serializer):
    text = serializers.CharField()
    use_evaluator = serializers.BooleanField(default=True)
    num_questions = serializers.IntegerField(required=False, default=10)
    answer_style = serializers.ChoiceField(choices=["all", "sentences", "multiple_choice"], default="all")

class GeneratedQuestionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedQuestions
        fields = ['id', 'user', 'entered_text', 'generated_questions', 'created_at']


