from datetime import timedelta
from datetime import datetime
import httplib2
import itertools
from apiclient.discovery import build
from oauth2client.client import OAuth2WebServerFlow
from apiclient.discovery import build
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run

CLIENT_SECRETS = 'auth.json'
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

def format_datetime(dt):
    return dt.strftime(TIME_FORMAT)

def parse_datetime(dt):
    return datetime.strptime(dt, TIME_FORMAT)

def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.izip(a, b)

def calculate_free_times(busy_times, start_time, end_time):
    busy_times = sorted(busy_times)
    tmp_first = None
    condensed_busy_times = []
    # Collapse adjecent time-blocks together into a single block
    for chunk1, chunk2 in pairwise(busy_times):
        if chunk1[1] >= chunk2[0]:
            if tmp_first is None:
                tmp_first = min(chunk1[1], chunk2[0])
        else:
            if tmp_first is None:
                condensed_busy_times.append(chunk1)
            else:
                condensed_busy_times.append((tmp_first, chunk1[1]))
                tmp_first = None
    if tmp_first is not None:
        condensed_busy_times.append((tmp_first, chunk2[1]))

    # Turn busy times into free times
    free_times = []
    for chunk1, chunk2 in pairwise(condensed_busy_times):
        if chunk1[0] == start_time or chunk2[1] == end_time:
            continue

        free_times.append((chunk1[1], chunk2[0]))
    return free_times

class Query(object):

    def __init__(self, start_time, end_time, *users):
        self.start_time = start_time
        self.end_time = end_time
        self.users = users

    def build_email_args(self):
        return [dict(id="%s@yelp.com" % user) for user in self.users]

    def build_time_args(self):
        return dict(
                timeMin=format_datetime(self.start_time),
                timeMax=format_datetime(self.end_time),
        )

class QueryResponse(object):
    def __init__(self, response):
        self.calendars = response['calendars']

    def get_cal(self, user):
        return self.calendars["%s@yelp.com" % user]['busy']

    def get_busy_times(self, user):
        cal = self.get_cal(user)
        busy_times = [(parse_datetime(dt_dict['start']), parse_datetime(dt_dict['end'])) for dt_dict in cal]
        return busy_times


def build_service():
    # Set up a Flow object to be used if we need to authenticate.
    FLOW = flow_from_clientsecrets(
            CLIENT_SECRETS,
            scope='https://www.googleapis.com/auth/calendar',
            message=""
    )
    storage = Storage('schedule.dat')

    credentials = storage.get()
    if credentials is None or credentials.invalid:
        credentials = run(FLOW, storage)

    # Create an httplib2.Http object to handle our HTTP requests and authorize it
    # with our good Credentials.
    http = httplib2.Http()
    http = credentials.authorize(http)

    service = build('calendar', 'v3', http=http)
    return service

def do_query(service, query):
    query_body = query.build_time_args()
    query_body['items'] = query.build_email_args()
    response = service.freebusy().query(body=query_body).execute()
    return QueryResponse(response)

def main():
    now = datetime.now()
    tomorrow = datetime.now() + timedelta(days=2)
    service = build_service()
    query = Query(now, tomorrow, 'abell', 'kylem', 'stop', 'ashleykb', 'tianyu')
    calendars = do_query(service, query)

    return calendars

if __name__ == '__main__':
    main()