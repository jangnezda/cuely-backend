import requests
import json
from . import modelsdocs
import inspect

class ClientDocs(object):
    def __init__(self):
        self.base_url = "https://docsapi.helpscout.net/v1/"
        self.api_key = ""
        self.pagestate = {}

    def articles(self, category_id, fields=None, **kwargs):
        url = add_fields("categories/{}/articles".format(category_id), fields)
        return self.page(url, "Article", 'articles', 200, **kwargs)

    def article(self, article_id, fields=None):
        url = add_fields("articles/{}".format(article_id), fields)
        return self.item(url, "Article", 200)

    def collections(self, fields=None, **kwargs):
        url = add_fields("collections", fields)
        return self.page(url, "Collection", 'collections', 200, **kwargs)

    def categories(self, collection_id,fields=None, **kwargs):
        url = add_fields("collections/{}/categories".format(collection_id), fields)
        return self.page(url, "Category", 'categories', 200, **kwargs)

    def call_server(self, url, expected_code, **params):
        headers = {'Content-Type': 'application-json',
                   'Accept' : 'application-json',
                   'Accept-Encoding' : 'gzip, deflate'
                  }

        req = requests.get('{}{}'.format(self.base_url, url),
                           headers=headers, auth=(self.api_key, 'x'), params=params)


        check_status_code(req.status_code, expected_code)

        return req.text

    def item(self, url, cls, expected_code):
        string_json = self.call_server(url, expected_code)
        return parse(json.loads(string_json)[cls.lower()], cls)

    def page(self, url, cls, page_cls, expected_code, **kwargs):
        # support calling many times to get subsequent pages
        caller = url

        if kwargs.get('page') is None:
            if caller in self.pagestate:
                (pcur, pmax) = [self.pagestate[caller].get(x) for x in ['page', 'pages']]
                if all((pcur, pmax)) and pcur < pmax:
                    kwargs['page'] = pcur + 1
                elif pcur == pmax:
                    return None

        string_json = self.call_server(url, expected_code, **kwargs)
        json_obj = json.loads(string_json)
        page = Page()
        for key, value in json_obj[page_cls].items():
            setattr(page, key, value)
        page.items = parse_list(page.items, cls)

        # update state cache with response details
        self.pagestate[caller] = {'page': page.page, 'pages': page.pages}
        return page

    def clearstate(self, function=None):
        '''Clear the function state tracking, optionally taking a specific function to clear
           Usage:
             client.reset()
             client.reset('users_for_mailbox')
        '''
        if function:
            if self.pagestate.pop(function, None) is None:
                return False
        else:
            self.pagestate = {}
        return True

def check_status_code(code, expected):
    status_codes = {
        '400': 'The request was not formatted correctly',
        '401': 'Invalid API Key',
        '402': 'API Key Suspended',
        '403': 'Access Denied',
        '404': 'Resource Not Found',
        '405': 'Invalid Method Type',
        '429': 'Throttle Limit Reached. Too many requests',
        '500': 'Application Error or Server Error',
        '503': 'Service Temporarily Unavailable'
        }
    if code == expected:
        return
    default_status = "Invalid API Key"
    status = status_codes[str(code)]
    if status != None:
        raise ApiException(status)
    else:
        raise ApiException(default_status)

def add_fields(url, fields):
    final_str = url
    if fields != None and len(fields) > 0:
        final_str = "{}?fields={}".format(url, ','.join(fields))
    return final_str

def parse(json_obj, cls):
    obj = getattr(modelsdocs, cls)()
    for key, value in list(json_obj.items()):
        setattr(obj, key.lower(), value)

    return obj

def parse_list(lst, cls):
    for i in range(len(lst)):
        lst[i] = parse(lst[i], cls)
    return lst

class Page:
    def __init__(self):
        self.page = None
        self.pages = None
        self.count = None
        self.items = None
    def __getitem__(self, index):
        return self.items[index]

    
class ApiException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
