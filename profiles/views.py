from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import routers, serializers, viewsets, generics
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django_filters import Filter
from rest_framework.views import APIView
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import AnonymousUser
import json

# import the api key
from decouple import config
import openai


# custom permissions
from .customPermission import ArtistManagerPermisson,CustomPermissionForClientAndPM,ProductManagerPermission

# serializers
from .serializers import *

# models
from .models import *



# ------------------------------ chat flow api ----------------------------------------------------
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
            return Response({'error': 'Something went wrong', 'error_message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------- create project api from chat flow ----------------------------------------------
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
            return Response({'success': 'Project created successfully','projectId':new_project.id},
             status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Something went wrong', 'error_message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self,request,*args, **kwargs):
        try:
            message = request.data['message']
            project_id = request.data['project_id']
            model_id = "text-ada-001"
            openai.api_key = config('OPENAI_API_KEY')
            project = get_object_or_404(Project,id = project_id)
            new_message = {
                'user':message
            }
            messageID = 1
            if project.brief in ["",None,"[]"]:
                new_message['msgID'] = messageID
                project.brief = f"[{json.dumps(new_message)}]"
            else:
                json_object = project.brief.replace("'",'"')
                json_object = json.loads(project.brief)
                messageID = int(json_object[-1]['msgID']) + 1
                new_message['msgID'] = messageID 
                brief = project.brief[:-1]
                brief += f",{json.dumps(new_message)}]"
                project.brief = brief
            completion = openai.Completion.create(
                prompt= message,
                max_tokens=1024,
                n=1,
                stop=None,
                temperature=0.7,
                model=model_id,
            )
            ans = completion.choices[0].text.strip()
            NewMessage = {
                'msgID':messageID + 1,
                'bot':ans,
            }
            brief = project.brief[:-1]
            brief += f",{json.dumps(NewMessage)}]"
            project.brief = brief
            project.save()
            project_serializer = ProjectSerializer(instance=project,many = False)
            return Response({'project':project_serializer.data,'success':'Project is updated!'},
            status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Something went wrong', 'error_message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# -------------------- standard pagination classes -------------------------------
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 1000

class RecommendedResultsSetPagination(PageNumberPagination):
    page_size = 3
    page_size_query_param = 'page_size'
    max_page_size = 100


# ------------------------------------ work feed api ---------------------------------
class WorkFeedViewSet(viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    serializer_class = WorkFeedSerializer
    filter_backends = [DjangoFilterBackend,filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['demo_type','owner', 'show_in_top_feed', 'owner__skill', 
    'owner__skill__genres', 'owner__location']

    search_fields = ['name', 'owner__name','owner__skill__name', 'owner__skill__genres__name']
    ordering_fields = '__all__'

    def get_queryset(self):
        work = Work.objects.filter(show_in_top_feed=True).order_by('show_in_top_feed')
        return work


#------------------------------- RecommendedResults api ------------------------------------
class GetRecommendationsViewSet(viewsets.ModelViewSet):
    pagination_class = RecommendedResultsSetPagination
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WorkFeedSerializer
    filter_backends = [DjangoFilterBackend,filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['demo_type',
                        'owner', 'show_in_top_feed', 'owner__skill', 'owner__skill__genres', 'owner__location']

    search_fields = ['name', 'owner__name',
                     'owner__skill__name', 'owner__skill__genres__name']
    ordering_fields = '__all__'

    def get_queryset(self):
        work = Work.objects.filter(owner__in=Client.objects.get(user=self.request.user).recommended_artists.all()).order_by('show_in_top_feed')
        return work


# -------------------------- template projects url -----------------------------
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

# ------------------------------------ project calculation ------------------------
def PorjectCalculation(project,data):
    if data['assigned_artist_payouts'] > 0:
        if project.solution_fee == 0 and project.production_advance == 0:
            project.assigned_artist_payouts = data['assigned_artist_payouts']
            project.solution_fee = float(data['assigned_artist_payouts'])*2.5
            project.production_advance = ((float(data['assigned_artist_payouts'])*2.5)/100)*30
            project.save()
            return True
    elif data['assigned_artist_payouts'] == 0:
        print(data['assigned_artist_payouts'])
        project.assigned_artist_payouts = 0.0
        project.solution_fee = 0.0
        project.production_advance = 0.0
        project.save()
        return True
    return False


class EditProjectViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ProjectSerializer

    def get_queryset(self):
        try:
            if not self.request.user.is_anonymous:
                return Project.objects.exclude(stage='DreamProject')
            return Project.objects.filter(stage='DreamProject')
        except Exception as e:
            return None

    def retrieve(self, request, pk=None):
        try:
            project = get_object_or_404(Project,pk=pk)
            if project.stage == 'DreamProject':
                return Response(self.serializer_class(project).data,status=status.HTTP_200_OK)
            elif not request.user.is_anonymous:
                if Role.objects.get(user = request.user).role in ['Client','Product Manager']:
                    return Response(self.serializer_class(project).data,status=status.HTTP_200_OK)
                return Response({'error':"you don't have permission to update"},
                status=status.HTTP_400_BAD_REQUEST)
            return Response({'error':'user is not logged in or project is not dream project'},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': 'Something went wrong', 'error_message': str(e)},
                            status=status.HTTP_401_UNAUTHORIZED)

    def update(self, request, pk=None):
        try:
            project = get_object_or_404(Project,pk=pk)
            data = request.data
            if "project_demo" in data:
                data['project_demo']['project'] = project.id
                data['project_demo']['status'] = 'Selected'
                projectDemo_serializer = ProjectDemoSerializer(data = data['project_demo'])
                if projectDemo_serializer.is_valid():
                    projectDemo_serializer.save()
                    project_demo = get_object_or_404(ProjectDemo,id = projectDemo_serializer.data['id'])
                    project.project_demos.add(project_demo)
                    project.save()
                    del data['project_demo']
                else:
                    return Response(projectDemo_serializer.error_messages,status=status.HTTP_400_BAD_REQUEST)
            if "assigned_artist_payouts" in data:
                calculation = PorjectCalculation(project, data)
                if calculation:
                    del data['assigned_artist_payouts']
            if project.stage == 'DreamProject':
                project_serializer = ProjectSerializer(instance=project,data = data)
                if project_serializer.is_valid():
                    project_serializer.save()
                    return Response(project_serializer.data,status=status.HTTP_200_OK)
                return Response(project_serializer.error_messages,status=status.HTTP_400_BAD_REQUEST)
            elif not request.user.is_anonymous:
                if Role.objects.get(user = request.user).role in ['Client','Product Manager']:
                    project_serializer = ProjectSerializer(instance=project,data = data)
                    if project_serializer.is_valid():
                        project_serializer.save()
                        return Response(project_serializer.data,status=status.HTTP_200_OK)
                    return Response(project_serializer.error_messages,status=status.HTTP_400_BAD_REQUEST)

                return Response({'error':"you don't have permission to update"},
                status=status.HTTP_400_BAD_REQUEST)
            return Response({'error':'user is not logged in or project is not dream project'},
                        status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response({'error': 'user is not logged in or project is not dream project', 
                             'error_message': str(e)},status=status.HTTP_401_UNAUTHORIZED)
    
    def partial_update(self, request, pk=None):
        try:
            project = get_object_or_404(Project,pk=pk)
            data = request.data
            if "project_demo" in data:
                data['project_demo']['project'] = project.id
                data['project_demo']['status'] = 'Selected'
                projectDemo_serializer = ProjectDemoSerializer(data = data['project_demo'])
                if projectDemo_serializer.is_valid():
                    projectDemo_serializer.save()
                    project_demo = get_object_or_404(ProjectDemo,id = projectDemo_serializer.data['id'])
                    project.project_demos.add(project_demo)
                    project.save()
                    del data['project_demo']
                else:
                    return Response(projectDemo_serializer.error_messages,status=status.HTTP_400_BAD_REQUEST)
            if "assigned_artist_payouts" in data:
                calculation = PorjectCalculation(project, data)
                if calculation:
                    del data['assigned_artist_payouts']
            if project.stage == 'DreamProject':
                project_serializer = ProjectSerializer(instance=project,data = data)
                if project_serializer.is_valid():
                    project_serializer.save()
                    return Response(project_serializer.data,status=status.HTTP_200_OK)
                return Response(project_serializer.error_messages,status=status.HTTP_400_BAD_REQUEST)
            elif not request.user.is_anonymous:
                if Role.objects.get(user = request.user).role in ['Client','Product Manager']:
                    project_serializer = ProjectSerializer(instance=project,data = request.data)
                    if project_serializer.is_valid():
                        project_serializer.save()
                        return Response(project_serializer.data,status=status.HTTP_200_OK)
                    return Response(project_serializer.error_messages,status=status.HTTP_400_BAD_REQUEST)
                return Response({'error':"you don't have permission to update"},status=status.HTTP_400_BAD_REQUEST)

            return Response({'error':'user is not logged in or project is not dream project'},
                        status=status.HTTP_400_BAD_REQUEST)
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




# ----------------------- all projects api -----------------------------
class AllProjectViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ProjectSerializerMini

    def get_queryset(self):
        role = Role.objects.get(user = self.request.user).role
        if role == 'Client':
            return Project.objects.filter(client__user=self.request.user).exclude(stage="DreamProject")
        elif role == 'Product Manager':
            return Project.objects.exclude(stage="DreamProject")
        return None

# ----------------------- all projects api end -----------------------------

# --------------------- update the project title api ---------------------------
class ProjectTitleViewSet(APIView):
    permission_classes = (permissions.AllowAny,) 
    
    def patch(self,request,id = None):
        try:
            if request.data['title'] in ['',None]:
                return Response({'error':'title not be empty'},status=status.HTTP_400_BAD_REQUEST)
            project = get_object_or_404(Project,id = id)
            project_serializer = ProjectSerializerMini(instance=project,data={'title':request.data['title']})
            if project_serializer.is_valid():
                project_serializer.save()
                return Response({'project':project_serializer.data},status=status.HTTP_200_OK)
            return Response(project_serializer.errors,status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error':'something went wrongs.','message':str(e)},status=status.HTTP_400_BAD_REQUEST)
# --------------------- update the project title api end ---------------------------



# ------------------------------- project assign api ------------------------------
class ProjectAssignArtistActionViewSet(APIView):
    permission_classes  = (permissions.IsAuthenticated,)

    def patch(self,request,projectId = None):
        try:
            project = get_object_or_404(Project,id = projectId)
            add_artists = request.data['add_artists']
            remove_artists = request.data['remove_artists']
            for artistId in add_artists:
                project.assigned_artists.add(artistId)
            for artistId in remove_artists:
                project.assigned_artists.remove(artistId)
            project.save()
            return Response({'project':ProjectSerializer(project,many=False).data,
                            'message':'Assign Artist is updated.'},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'message':'something wents wrong!','error':str(e)},status=status.HTTP_400_BAD_REQUEST)


#-------------------------------- shortlisted artist api -------------------------------
class ProjectShortlistedArtistViewSet(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def patch(self,request,projectId = None,artistId = None):
        try:
            project = get_object_or_404(Project,id = projectId)
            artist = get_object_or_404(Artist,id = artistId)
            project.shortlisted_artists.add(artist)
            project.save()
            return Response({'project':ProjectSerializer(project,many=False).data,
                            'message':'Assign Artist is updated.'},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'message':'something wents wrong!','error':str(e)},status=status.HTTP_400_BAD_REQUEST)

#-------------------------------- shortlisted artist api -------------------------------

# ---------------------------------- remove shortlisted artist api ----------------------------
class ProjectShortlistedArtistRemoveViewSet(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def patch(self,request,projectId = None,artistId = None):
        try:
            project = get_object_or_404(Project,id = projectId)
            artist = get_object_or_404(Artist,id = artistId)
            project.shortlisted_artists.remove(artist)
            project.save()
            return Response({'project':ProjectSerializer(project,many=False).data,
                            'message':'Assign Artist is updated.'},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'message':'something wents wrong!','error':str(e)},status=status.HTTP_400_BAD_REQUEST)

#--------------------------------remove shortlisted artist api -------------------------------

# ------------------------------ assign artist ---------------------------------
class ProjectAssignArtistViewSet(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def patch(self,request,projectId = None,artistId = None):
        try:
            project = get_object_or_404(Project,id = projectId)
            artist = get_object_or_404(Artist,id = artistId)
            if not project.shortlisted_artists.filter(id = artistId).exists():
                return Response({'message':'artist is not shortlisted at.'},status=status.HTTP_400_BAD_REQUEST)
            project.shortlisted_artists.remove(artist)
            project.assigned_artists.add(artist)
            project.save()
            return Response({'project':ProjectSerializer(project,many=False).data,
                            'message':'Assign Artist is updated.'},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'message':'something wents wrong!','error':str(e)},status=status.HTTP_400_BAD_REQUEST)
            

# ------------------------------ unassign artist ---------------------------------
class ProjectUnAssginArtistViewSet(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    def patch(self,request,projectId = None,artistId = None):
        try:
            project = get_object_or_404(Project,id = projectId)
            artist = get_object_or_404(Artist,id = artistId)
            if not project.assigned_artists.filter(id = artistId).exists():
                return Response({'message':'artist is not assigned at.'},status=status.HTTP_400_BAD_REQUEST)
            project.assigned_artists.remove(artist)
            project.shortlisted_artists.add(artist)
            project.save()
            return Response({'project':ProjectSerializer(project,many=False).data,
                            'message':'Assign Artist is updated.'},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'message':'something wents wrong!','error':str(e)},status=status.HTTP_400_BAD_REQUEST)


# ------------------------------- project assign api ------------------------------


# -------------------------- create new Porject --------------------------------------
class CreateNewProject(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self,request):
        try:
            data = request.data
            client = get_object_or_404(Client,user = request.user)
            data['client'] = client.id
            project_serializer = ProjectSerializer(data = data)
            if project_serializer.is_valid():
                project_serializer.save()
                return Response(project_serializer.data,status=status.HTTP_201_CREATED)
            return Response(project_serializer.error_messages,status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'message':'something wents wrong!','error':str(e)},status=status.HTTP_400_BAD_REQUEST)


# ---------------------------- demo project -----------------------------------------
class DemoView(APIView):
    permission_classes = (IsAuthenticated,ArtistManagerPermisson,)

    def get(self,request):
        work = WorkFeedSerializer(Work.objects.all(),many=True)
        return Response({'works':work.data,'message':'for permission check'},status=status.HTTP_200_OK)

# ---------------------------- demo project end -----------------------------------------

# chatgpt integration
class OpenAIViewSet(APIView):
    def post(self,request):
        try:
            data = request.data
            project = get_object_or_404(Project,id = data['project_id'])
            model_id = "text-ada-001"
            openai.api_key = config('OPENAI_API_KEY')
            print(config('OPENAI_API_KEY'))
            completion = openai.Completion.create(
                prompt= project.brief,
                max_tokens=1024,
                n=1,
                stop=None,
                temperature=0.7,
                model=model_id,
            )
            ans = completion.choices[0].text.strip()
            NewMessage = {
                'msgId':1,
                'bot':ans,
            }
            return Response({'response':ans,'brief':project.brief},status= status.HTTP_200_OK)
        except Exception as e:
            return Response({'error':str(e)},status=status.HTTP_400_BAD_REQUEST)