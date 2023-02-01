
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import routers, serializers, viewsets, generics
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django_filters import Filter
from rest_framework.views import APIView
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
import json
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import AnonymousUser


# custom permissions
from .customPermission import ArtistManagerPermisson

# serializers
from .serializers import *

# models
from .models import *


class chatflowSkills(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        try:
            data = request.data
            artists = data['artists']
            product = data['product']

            skills = []
            possible_projects = []
            # print intersecting skills of artists
            if artists in [0, '0', None, '']:
                if product in [0, '0', None, '']:
                    return Response({'skills': [], 'projects': []}, status=status.HTTP_200_OK)
                else:
                    return Response({'skills': [
                        [skill.name, skill.id] for skill in TemplateProjects.objects.get(id=int(product)).skills.all()],
                         'projects': TemplateProjects.objects.filter(pk=product).values_list('name', 'id')},
                          status=status.HTTP_200_OK)
            for artist in artists.split(','):
                artist_skills = Artist.objects.get(pk=artist).skill.all()
                for skill in artist_skills:
                    if [skill.name, skill.id] not in skills:
                        skills.append([skill.name, skill.id])

            print(skills)

            if product in [0, '0', None, '']:

                for project in TemplateProjects.objects.all():
                    for skill in project.skills.all():
                        if [skill.name, skill.id] in skills:
                            possible_projects.append(
                                [project.name, project.id])
            else:
                return Response({'skills': [
                    [skill.name, skill.id] for skill in TemplateProjects.objects.get(id=int(product)).skills.all()],
                     'projects': TemplateProjects.objects.filter(pk=product).values_list('name', 'id')}, status=status.HTTP_200_OK)

            return Response({'skills': skills, 'projects': possible_projects}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'error': 'Something went wrong', 'error_message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# create project api
class CreateProjectView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        try:
            data = request.data
            artists = data['shortlisted_artists']
            product = data['product']
            brief = data['brief']
            stage = data['stage']

            if artists in [0, '0', None, '']:
                return Response({'error': 'Please select an artist'}, status=status.HTTP_200_OK)
            if product in [0, '0', None, '']:
                return Response({'error': 'Please select a product'}, status=status.HTTP_200_OK)
            if brief in [0, '0', None, '']:
                return Response({'error': 'Please send a brief message '}, status=status.HTTP_200_OK)

            # create project
            project = TemplateProjects.objects.get(pk=product)
            new_project = Project.objects.create(
                stage=stage,
                brief=brief, 
                project_template=project, 
                client=Client.objects.get(user=request.user))

            # add artists
            for artist in artists:
                new_project.shortlisted_artists.add(Artist.objects.get(pk=artist))

            new_project.save()
            return Response({'success': 'Project created successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'error': 'Something went wrong', 'error_message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self,request,*args, **kwargs):
        try:
            message = request.data['message']
            project_id = request.data['project_id']


            if not Project.objects.filter(id = project_id).exists():
                return Response({'error':'please send the proper project id'},status=status.HTTP_400_BAD_REQUEST)
            
            project = get_object_or_404(Project,id = project_id)
            brief = project.brief[:-1]
            brief += f",{json.dumps(message)}]"
            project.brief = brief
            project.save()

            project_serializer = ProjectSerializer(instance=project,many = False)
            return Response({'project':project_serializer.data,'success':'Project is updated!'},
            status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': 'Something went wrong', 'error_message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class WorkFeedViewSet(viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    serializer_class = WorkFeedSerializer
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['demo_type',
                        'owner', 'show_in_top_feed', 'owner__skill', 'owner__skill__genres', 'owner__location']

    search_fields = ['name', 'owner__name',
                     'owner__skill__name', 'owner__skill__genres__name']
    ordering_fields = '__all__'

    def get_queryset(self):

        work = Work.objects.filter(
            show_in_top_feed=True).order_by('show_in_top_feed')

        return work


class RecommendedResultsSetPagination(PageNumberPagination):
    page_size = 3
    page_size_query_param = 'page_size'
    max_page_size = 100

class GetRecommendationsViewSet(viewsets.ModelViewSet):
    pagination_class = RecommendedResultsSetPagination
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WorkFeedSerializer
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['demo_type',
                        'owner', 'show_in_top_feed', 'owner__skill', 'owner__skill__genres', 'owner__location']

    search_fields = ['name', 'owner__name',
                     'owner__skill__name', 'owner__skill__genres__name']
    ordering_fields = '__all__'

    def get_queryset(self):
        work = Work.objects.filter(owner__in=Client.objects.get(user=self.request.user).recommended_artists.all()).order_by('show_in_top_feed')

        return work


class TemplateProjectViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.AllowAny,)
    serializer_class = TemplateProjectsSerializer

    def get_queryset(self):
        return TemplateProjects.objects.all()


class MyProjectsViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ProjectSerializerMini

    def get_queryset(self):
        return Project.objects.filter(client__user=self.request.user, stage='Lead')


class GetDreamProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializerMini

    def get_queryset(self):
        return Project.objects.filter(stage='DreamProject')


class EditProjectViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ProjectSerializer

    def get_queryset(self):
        try:
            if not self.request.user.is_anonymous:
                return Project.objects.filter(client__user=self.request.user)
            return Project.objects.filter(stage='DreamProject')
        except Exception as e:
            return None

    def retrieve(self, request, pk=None):
        try:
            if pk is None:
                return Response({'error':'Please send the id.'},status=status.HTTP_400_BAD_REQUEST)
            if Project.objects.filter(pk=pk).exists():
                project = Project.objects.get(pk=pk)
                if project.stage == 'DreamProject':
                    return Response(self.serializer_class(project).data,status=status.HTTP_200_OK)
                else:
                    if not request.user.is_anonymous:
                        project = get_object_or_404(Project,pk=pk,client__user=self.request.user)
                        return Response(self.serializer_class(project).data,status=status.HTTP_200_OK)

            return Response({'error':'user is not logged in or project is not dream project'},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': 'Something went wrong', 'error_message': str(e)},
                            status=status.HTTP_401_UNAUTHORIZED)

    def update(self, request, pk=None):
        try:
            if pk is None:
                return Response({'error':'Please send the id.'},status=status.HTTP_400_BAD_REQUEST)
            if Project.objects.filter(pk=pk).exists():
                project = Project.objects.get(pk=pk)
                if project.stage == 'DreamProject':
                    project_serializer = ProjectSerializer(instance=project,data = request.data)
                    if project_serializer.is_valid():
                        project_serializer.save()
                        return Response(project_serializer.data,status=status.HTTP_200_OK)
                    return Response(project_serializer.error_messages,status=status.HTTP_200_OK)
                else:
                    if not request.user.is_anonymous:
                        project = get_object_or_404(Project,pk=pk,client__user=self.request.user)
                        project_serializer = ProjectSerializer(instance=project,data = request.data)
                        if project_serializer.is_valid():
                            project_serializer.save()
                            return Response(project_serializer.data,status=status.HTTP_200_OK)
                        return Response(project_serializer.error_messages,status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'user is not logged in or project is not dream project', 
                             'error_message': str(e)},status=status.HTTP_401_UNAUTHORIZED)
    
    def partial_update(self, request, pk=None):
        try:
            if pk is None:
                return Response({'error':'Please send the id.'},status=status.HTTP_400_BAD_REQUEST)
            if Project.objects.filter(pk=pk).exists():
                project = Project.objects.get(pk=pk)
                if project.stage == 'DreamProject':
                    project_serializer = ProjectSerializer(instance=project,data = request.data)
                    if project_serializer.is_valid():
                        project_serializer.save()
                        return Response(project_serializer.data,status=status.HTTP_200_OK)
                    return Response(project_serializer.error_messages,status=status.HTTP_200_OK)
                else:
                    if not request.user.is_anonymous:
                        project = get_object_or_404(Project,pk=pk,client__user=self.request.user)
                        project_serializer = ProjectSerializer(instance=project,data = request.data)
                        if project_serializer.is_valid():
                            project_serializer.save()
                            return Response(project_serializer.data,status=status.HTTP_200_OK)
                        return Response(project_serializer.error_messages,status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'user is not logged in or project is not dream project', 
                             'error_message': str(e)},status=status.HTTP_401_UNAUTHORIZED)


# ====================== delete project api ==============================
class ProjectDeleteViewSet(APIView):
    permission_classes = (permissions.AllowAny,)
    def delete(self,request,pk,format=None):
        try:
            if not Project.objects.filter(id = pk).exists():
                return Response({'error':'project Not Found'},status=status.HTTP_404_NOT_FOUND)
            project = get_object_or_404(Project,id = pk)
            project.delete()
            return Response({'message':'project is deleted'},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'something went wrong', 
                             'error_message': str(e)},status=status.HTTP_401_UNAUTHORIZED)


# ================== artist manager API's =======================
class ArtistViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ArtistProfileSerializer

    filter_backends = [DjangoFilterBackend,filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['skill', 'languages', 'location']
    skill = Filter(name="skill", lookup_type='in')
    language = Filter(name="languages", lookup_type='in')

    search_fields = ['name', 'location__name','skill__name', 'languages__name']
    ordering_fields = '__all__'

    def get_queryset(self):
        profile = Artist.objects.filter()
        return profile

# ====================== artist action ===================================
class ArtistActionviewSet(APIView):
    permission_classes = (permissions.AllowAny,)
    filter_backends = [DjangoFilterBackend,filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['skill', 'languages', 'location']
    skill = Filter(name="skill", lookup_type='in')
    language = Filter(name="languages", lookup_type='in')
    search_fields = ['name', 'location__name','skill__name', 'languages__name']
    ordering_fields = '__all__'

    def get(self,request,*args, **kwargs):
        try:
            id = request.query_params.get('id', None)
            if id is not None:
                artists = get_object_or_404(Artist,id = id)
                artist_serializer = ArtistFilterSerializer(artists,many = False)
                return Response({'artists':artist_serializer.data},status=status.HTTP_200_OK)
            artists = Artist.objects.all()
            artist_serializer = ArtistFilterSerializer(artists,many = True)
            return Response({'artists':artist_serializer.data},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': "something went's Wrong!", 'error_message': str(e)},status=status.HTTP_400_BAD_REQUEST)

    def post(self,request,*args, **kwargs):
        try:
            data = request.data
            if data['has_manager']:
                manager = Manager.objects.create(name= data['manager']['name'],phone= data['manager']['phone'],
                email = data['manager']['email'])
                data['manager'] = manager.id
            works_links = data['works_links']
            del data['works_links']
            works = []
            artist_serializer = ArtistActionSerializer(data = request.data)
            if artist_serializer.is_valid():
                artist_serializer.save()
                artist = Artist.objects.get(id = artist_serializer.data['id'])
                for work_link in works_links:
                    work = Work.objects.create(owner = artist,demo_type=work_link['demo_type'],
                    weblink=work_link['weblink'])
                    works.append(work.id)
                artist.works_links.set(works)
                return Response({'artist':ArtistFilterSerializer(instance=artist,many=False).data,
                'message':'artist is created'},status=status.HTTP_201_CREATED)
            return Response(serializers.errors,status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response({'error': "something went's Wrong!", 'error_message': str(e)},status=status.HTTP_400_BAD_REQUEST)

    def put(self,request,pk = None):
        try:
            if pk is None:
                return Response({'error':'artist not found with empty id!'},status=status.HTTP_404_NOT_FOUND)
            artist = get_object_or_404(Artist,id = pk)
            artist_serializer = ArtistActionSerializer(instance=artist,data = request.data)
            if artist_serializer.is_valid():
                artist_serializer.save()
                new_artist = ArtistFilterSerializer(instance=Artist(id = artist.id),many=False)
                return Response({'artist':new_artist,'message':'artist is created'},status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': "something went's Wrong!", 'error_message': str(e)},status=status.HTTP_400_BAD_REQUEST)


# ================= product manager API's =======================
class ArtistFeedBackViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ArtistFeedbackSerializer
    queryset = ArtistFeedback.objects.all()


class ProjectFeeViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ProjectFeeSerializers
    queryset = ProjectFee.objects.all()


class ArtistRequestViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ArtistRequestSerializers
    queryset = ArtistRequest.objects.all()

#==== demo purpose =====
class DemoView(APIView):
    permission_classes = (IsAuthenticated,ArtistManagerPermisson,)

    def get(self,request):
        return Response({'message':'for permission check'},status=status.HTTP_200_OK)
