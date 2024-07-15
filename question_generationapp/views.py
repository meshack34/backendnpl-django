from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from django.contrib.auth import authenticate, get_user_model
from rest_framework.authtoken.models import Token
from .serializers import RegisterSerializer, LoginSerializer, UserDetailSerializer, QuestionGenerationSerializer, GeneratedQuestionsSerializer
from .models import Account, GeneratedQuestions
from questiongenerator import QuestionGenerator
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = Account.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer
    

class LoginView(APIView):
    permission_classes = (AllowAny,)
    
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        user = authenticate(email=email, password=password)
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'is_admin': user.is_admin,
                'is_staff': user.is_staff,
                'is_active': user.is_active,
                'is_superadmin': user.is_superadmin,
            }, status=status.HTTP_200_OK)
        return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)


class UserDetailView(RetrieveUpdateAPIView):
    serializer_class = UserDetailSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user.user_profile  # Get the related UserProfile object


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
