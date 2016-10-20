from django.http import JsonResponse


def ping(request):
    return JsonResponse({
        'status': 'Ok',
        'message': 'Ping successful'
    })
