from rest_framework import serializers
from .models import Account, UserProfile, GeneratedQuestions

class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'email', 'first_name', 'last_name', 'username', 'phone_number', 'user_type', 'date_joined', 'last_login', 'is_admin', 'is_staff', 'is_active', 'is_superadmin']

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['email', 'first_name', 'last_name', 'username', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = Account.objects.create_user(
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            username=validated_data['username'],
            password=validated_data['password']
        )
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['city', 'address', 'country', 'gender', 'blood_group', 'date_of_birth', 'age_years']
        read_only_fields = ['user']  # Ensure user cannot update their own user field

    def update(self, instance, validated_data):
        instance.city = validated_data.get('city', instance.city)
        instance.address = validated_data.get('address', instance.address)
        instance.country = validated_data.get('country', instance.country)
        instance.gender = validated_data.get('gender', instance.gender)
        instance.blood_group = validated_data.get('blood_group', instance.blood_group)
        instance.date_of_birth = validated_data.get('date_of_birth', instance.date_of_birth)
        instance.age_years = validated_data.get('age_years', instance.age_years)
        instance.save()
        return instance

# class QuestionGenerationSerializer(serializers.Serializer):
#     text = serializers.CharField()
#     use_evaluator = serializers.BooleanField(default=True)
#     num_questions = serializers.IntegerField(required=False, default=10)
#     answer_style = serializers.ChoiceField(choices=["all", "sentences", "multiple_choice"], default="all")

class GeneratedQuestionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedQuestions
        fields = ['id', 'user', 'entered_text', 'generated_questions', 'created_at']
        
class QuestionGenerationSerializer(serializers.Serializer):
    text = serializers.CharField()
    use_evaluator = serializers.BooleanField(default=True)
    num_questions = serializers.IntegerField(required=False, default=10)
    answer_style = serializers.ChoiceField(choices=["all", "sentences", "multiple_choice"], default="all")
