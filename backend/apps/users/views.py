from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.shortcuts import get_object_or_404

from apps.core.permissions import IsResearcher, IsStudyManager

from .roles import HUMAN_RATER_GROUP
from .serializers import (
    RaterCreateSerializer,
    RaterUpdateSerializer,
    UserSerializer,
)

User = get_user_model()


class MeView(APIView):
    permission_classes = [IsResearcher]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class RaterListCreateView(APIView):
    permission_classes = [IsStudyManager]

    def get(self, request):
        raters = (
            User.objects.filter(groups__name=HUMAN_RATER_GROUP)
            .annotate(rating_count=Count("ratings"))
            .order_by("username")
        )
        return Response(UserSerializer(raters, many=True).data)

    def post(self, request):
        serializer = RaterCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class RaterDetailView(APIView):
    permission_classes = [IsStudyManager]

    def patch(self, request, pk):
        user = get_object_or_404(
            User.objects.filter(groups__name=HUMAN_RATER_GROUP), pk=pk
        )
        serializer = RaterUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data)
