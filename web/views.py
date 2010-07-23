import datetime

from django import http
from django.shortcuts import render_to_response
from django.utils import simplejson
# from django.template import Context, Template
from django.conf import settings
from django.db.models.query import QuerySet

from norc.core import report
from norc.norc_utils.parsing import parse_since
from norc.norc_utils.web import JSONObjectEncoder, paginate
# from norc.core.models import NorcDaemonStatus
from norc.web.structure import \
    RETRIEVE, RETRIEVE_DETAILS, DATA, SINCE_FILTER, ORDER

def index(request):
    """Returns the index.html template."""
    return render_to_response('index.html', {
        'sqs': 'norc.sqs' in settings.INSTALLED_APPS,
    })

def get_data(request, content_type, content_id=None):
    """Retrieves and structures data, then returns it as a JSON object.
    
    Returns a JSON object containing data on given content type.
    If content_id is provided, data on the details of the content_type
    object associated with that id will be returned.  The data is
    filtered by GET parameters in the request.
    
    """
    if content_id == None:
        data_key = content_type
        data_set = RETRIEVE[content_type]()
    else:
        data_key, data_getter = RETRIEVE_DETAILS[content_type]
        # Turrible temporary hackage to get SQS stuff on the frontend.
        if data_key == 'tasks':
            d = report.nds(content_id)
            if d.get_daemon_type() == 'SQS':
                data_key = 'sqstasks'
        # End the ugly.
        data_set = data_getter(content_id, request.GET)
    
    if 'since' in request.GET and type(data_set) == QuerySet:
        since_date = parse_since(request.GET['since'])
        if since_date and data_key in SINCE_FILTER:
            data_set = SINCE_FILTER[data_key](data_set, since_date)
        # try:
        #     data_set = data_set.filter(date_started__gte=since_date)
        # except Exception:
        #     pass
    if data_key in ORDER:
        data_set = ORDER[data_key](data_set, request.GET.get('order'))
    page, page_data = paginate(request, data_set)
    json_data = {'data': [], 'page': page_data}
    for obj in page.object_list:
        obj_data = {}
        for key, ret_func in DATA[data_key].iteritems():
            obj_data[key] = ret_func(obj, request.GET)
        json_data['data'].append(obj_data)
    json = simplejson.dumps(json_data, cls=JSONObjectEncoder)
    return http.HttpResponse(json, mimetype="json")
