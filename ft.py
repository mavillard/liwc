
# coding: utf-8

# #Sentence extractor for The Financial Times

# In[1]:

import logging
import math
import os
from collections import defaultdict
from datetime import timedelta, date, datetime
from dateutil import parser
from time import sleep, time

import requests
import yaml
from joblib import Parallel, delayed
from pymongo import MongoClient
from pymongo.errors import BulkWriteError, DuplicateKeyError


# ##Logging

# In[2]:

try:
    os.remove('search_ft.log')
except:
    pass


# In[3]:

logging.getLogger().handlers = []
logging.getLogger('requests.packages.urllib3').setLevel(logging.WARNING)
logging.basicConfig(filename='search_ft.log', level=logging.INFO, format='%(asctime)s %(message)s')


# In[4]:

def write_log(*args, status=None):
    record = '{} ==> {}'.format(args, status)
    logging.info(record)


# ##MongoDB

# In[5]:

client = MongoClient()
client.drop_database('ft')
db = client.ft


# In[6]:

def update_document(_id, new_q_info):
    doc = db.articles.find_one({'_id': _id})
    new_orig_term = list(new_q_info.keys())[0]
    if new_orig_term in doc['q_info']:
        doc['q_info'][new_orig_term].extend(new_q_info[new_orig_term])
    else:
        doc['q_info'].update(new_q_info)
    db.articles.update({'_id': _id}, {'$set': {'q_info': doc['q_info']}})

def insert_documents(docs, q):
    try:
        inserted = db.articles.insert_many(docs, ordered=False)
        total_inserted = len(inserted.inserted_ids)
        write_log(q, status='INSERTION OK {}'.format(total_inserted))
    except BulkWriteError as e:
        n_updated = 0
        for err in e.details['writeErrors']:
            if err['code'] == 11000:
                try:
                    _id = err['op']['_id']
                    new_q_info = err['op']['q_info']
                    update_document(_id, new_q_info)
                    n_updated += 1
                except Exception as ex:
                    write_log(q, status='UPDATE EXCEPTION {} - {}'.format(err['errmsg'], ex))
        write_log(q, status='INSERTION OK {}'.format(e.details['nInserted']))
        write_log(q, status='UPDATE OK {}'.format(n_updated))
    except Exception as e:
        write_log(q, status='INSERTION EXCEPTION {}'.format(e))


# ##Search terms

# In[7]:

def preprocess_term(term):
    terms = []
    
    curated_term = term.lower()
    curated_term = curated_term.replace(' & ', ' ')
    curated_term = curated_term.replace(' and ', ' ')
    curated_term = curated_term.replace('-', ' ')
    terms.append(curated_term)
    
    for term in terms:
        if term.endswith('corporation'):
            terms.append(term[:-12])
        elif term.endswith('corp'):
            terms.append(term[:-5])
        elif term.endswith('company'):
            terms.append(term[:-8])
        elif term.endswith('inc.'):
            terms.append(term[:-5])
        elif term.endswith('inc'):
            terms.append(term[:-4])
        elif term.endswith('.com'):
            terms.append(term[:-4])
    
    return terms


# In[8]:

term_dict = {}
for i in range(1, 4):
    term_dict[i] = {}
    st_file = open('search_terms_{}.txt'.format(i))
    term_list = map(lambda x: x.strip(), st_file.readlines())
    for term in term_list:
        term_dict[i][term] = preprocess_term(term)


# In[9]:

with open('search_terms_ft.yml', 'w') as search_term_file:
    search_term_file.write(yaml.dump(term_dict, default_flow_style=False))


# In[10]:

with open('search_terms_ft.yml') as search_term_file:
    term_yaml = yaml.load(search_term_file.read())


# ##FT API keys

# In[11]:

# One API key for each of the cores
api_keys = [
    "mtqjgqpd63c5aky6ujz7mfe4", # Antonio
    "zb3atmjyfth2ehgzbr94nkq2", # Antonio 2
    "d67kd552dhk4spqhjnx2kzz8", # Javi
    "x6f2ydhhyuv9exjresaxq347", # David
    "gtya39yhnt3uz558s9hf8aqs", # Gabi
    "85uppscwzvjbx8w8bekvfs2k", # Nandi
    "mf5k3xz7v7f66jcx6yx7g2q3", # Adri
    "warj9jjwsuayfqajgggf7ac8", # Pedro
]


# In[12]:

def next_multiple(n, m):
    # 4, 17 ==> 20
    return math.ceil(m / n) * n

def chunks(l, n_chunks):
    l = list(l)
    size = len(l)
    n = next_multiple(n_chunks, size) // n_chunks
    for i in range(0, size, n):
        yield l[i:i + n]


# In[13]:

# [(search_term, original_term, term_type)]
search_terms = [(t, k2, k1)
                   for k1 in term_yaml
                       for k2 in term_yaml[k1]
                           for t in term_yaml[k1][k2]
              ]


# In[14]:

# TEST

# api_keys = [
#     "mf5k3xz7v7f66jcx6yx7g2q3", # Adri
#     "warj9jjwsuayfqajgggf7ac8", # Pedro
# ]

# search_terms = [
#     ('entrepreneur', 'entrepreneur', 1),
#     ('executive', 'executive', 1),
#     ('google', 'google', 2),
#     ('amazon', 'amazon.com', 2),
#     ('amazon.com', 'amazon.com', 3),
#     ('ebay', 'e-bay', 3),
# ]

# BEGIN_DATE = date(2014, 1, 1)
# END_DATE = date(2014, 2, 28)


# In[15]:

search_terms_by_api_key = defaultdict(list)
for i in range(1, 4):
    search_terms_i = list(filter(lambda x: x[2] == i, search_terms))
    for t in zip(api_keys, chunks(search_terms_i, len(api_keys))):
        search_terms_by_api_key[t[0]].extend(t[1])


# ##Dates

# In[16]:

def month_duration(d):
    if d.month in [1, 3, 5, 7, 8, 10, 12]:
        ndays = 31
    elif d.month in [4, 6, 9, 11]:
        ndays = 30
    else: # d.month == 2
        if d.year % 400 == 0 or d.year % 4 == 0 and d.year % 100 != 0: # lap-year
            ndays = 29
        else:
            ndays = 28
    return ndays

def n_days(d, n_months):
    ndays = 0
    new_d = d
    for _ in range(n_months):
        m_duration = month_duration(d)
        d += timedelta(m_duration)
        ndays += m_duration
    return ndays - 1

def date_ranges(begin_date, end_date, n_months=1):
    aux_date = begin_date
    while aux_date < end_date:
        ndays = n_days(aux_date, n_months)
        yield (aux_date, min(aux_date + timedelta(ndays + 1), end_date))
        aux_date += timedelta(ndays + 1)


# ##Timer

# In[17]:

LAST_REQUEST = time()


# In[18]:

def wait(f, *args, t=9):
    global LAST_REQUEST
    now = time()
    elapsed_time = now - LAST_REQUEST
    if elapsed_time < t:
        sleep(t - elapsed_time)
    LAST_REQUEST = time()
    return f(*args)


# ##Query

# In[19]:

class Query:
    def __init__(self, term, begin_date, end_date, offset, api_key):
        self.term = term
        self.begin_date = begin_date
        self.end_date = end_date
        self.offset = offset
        self.api_key =api_key
    
    def __repr__(self):
        return 'Q<{}, {}, {}, {}, {}>'.format(self.term, self.begin_date, self.end_date, self.offset, self.api_key)


# ##Downloader

# In[20]:

BEGIN_DATE = date(1999, 1, 1)
END_DATE = date(2014, 12, 31)


# In[21]:

def search(q):
    try:
        base_url = 'http://api.ft.com/content/search/v1'
        payload = {'apiKey': q.api_key}
        data = {
            'queryString': '{} AND initialPublishDateTime:>{} AND initialPublishDateTime:<{}'.format(
                q.term,
                q.begin_date + 'T00:00:00Z',
                q.end_date + 'T00:00:00Z',
            ),
            'resultContext': {
                'aspects': ["title","lifecycle","location","summary","editorial"],
                'offset': q.offset,
                'sortOrder' : 'ASC',
                'sortField' : 'initialPublishDateTime'
            }
        }
        r = requests.post(base_url, params=payload, json=data)
        response = r.json()
        response['status'] = r.reason
        
        if response['results']:
            write_log(q, status='SEARCH OK {}'.format(response['results'][0]['indexCount']))
        else:
            write_log(q, status='SEARCH ERROR')
    except ValueError as e:
        if str(e) == 'Expecting value: line 1 column 1 (char 0)':
            write_log(q, status='SEARCH ERROR api-key')
        else:
            write_log(q, status='SEARCH EXCEPTION {}'.format(e))
        response = {'status': r.reason}
    except Exception as e:
        write_log(q, status='SEARCH EXCEPTION {}'.format(e))
        response = {'status': r.reason}
    return response


# In[22]:


# base_url = 'http://api.ft.com/content/search/v1'
# payload = {'apiKey': "mtqjgqpd63c5aky6ujz7mfe4"}
# data = {
#     'queryString': '{} AND initialPublishDateTime:>{} AND initialPublishDateTime:<{}'.format(
#         'executive',
#         "2014-01-01" + 'T00:00:00Z',
#         "2014-01-07" + 'T00:00:00Z',
#     ),
#     'resultContext': {
#         'aspects': ["title","lifecycle","location","summary","editorial"],
#         'offset': 0,
#         'sortOrder' : 'ASC',
#         'sortField' : 'initialPublishDateTime'
#     }
# }
# r = requests.post(base_url, params=payload, json=data)
# response = r.json()
# response['status'] = r.reason


# In[23]:

# response


# In[24]:

def get_documents_by_offset(q, term, total_results):
    n_pages = math.ceil(total_results / 100)
    for page in range(n_pages):
        q.offset = page * 100
        response = wait(search, q)
        
        if response['status'] == 'OK':
            docs = response['results'][0]['results']
            for doc in docs:
                doc['_id'] = doc.pop('id')
                orig_term = term[1].replace('.', '_')
                doc.update({'q_info': {orig_term: [{'q': q.__dict__, 'term_category': term[2]}]}})
                # TODO: filter fields ... DO NOT FILTER
            insert_documents(docs, q)


# In[25]:

def get_documents_by_query(q, term):
    response = wait(search, q)
    
    if response['status'] == 'OK':
        total_results = response['results'][0]['indexCount']
        if total_results <= 4000:
            get_documents_by_offset(q, term, total_results)
        else:
            bd = parser.parse(q.begin_date)
            ed = parser.parse(q.end_date)
            half = (ed - bd) // 2
            
            begin_date1 = q.begin_date
            end_date1 = (bd + timedelta(half.days)).strftime("%Y-%m-%d")
            q1 = Query(q.term, begin_date1, end_date1, 0, q.api_key)
            get_documents_by_query(q1, term)
            
            begin_date2 = (bd + timedelta(half.days + 1)).strftime("%Y-%m-%d")
            end_date2 = q.end_date
            q2 = Query(q.term, begin_date2, end_date2, 0, q.api_key)
            get_documents_by_query(q2, term)


# In[26]:

def download_by_date_ranges(term, api_key):
    for r in date_ranges(BEGIN_DATE, END_DATE, 1):
        begin_date = r[0].strftime("%Y-%m-%d")
        end_date = r[1].strftime("%Y-%m-%d")
        q = Query(term[0], begin_date, end_date, 0, api_key)
        get_documents_by_query(q, term)


# In[27]:

def download_by_term(term, api_key):
    begin_date = BEGIN_DATE.strftime("%Y-%m-%d")
    end_date = END_DATE.strftime("%Y-%m-%d")
    q = Query(term[0], begin_date, end_date, 0, api_key)
    response = wait(search, q)
    
    if response['status'] == 'OK':
        total_results = response['results'][0]['indexCount']
        if total_results <= 4000:
            get_documents_by_offset(q, term, total_results)
        else:
            download_by_date_ranges(term, api_key)


# In[28]:

def download_by_key(terms, api_key):
    for term in terms:
        try:
            download_by_term(term, api_key)
        except Exception as e:
            write_log(e, status='DOWNLOAD EXCEPTION {} {}'.format(term, api_key))


# In[29]:

def downloader(search_terms_by_api_key, api_keys):
    # Version parallel
    Parallel(n_jobs=8)(delayed(download_by_key)(search_terms_by_api_key[api_key], api_key) for api_key in api_keys)

    # Version sequencial
#     for api_key in api_keys:
#         download_by_key(search_terms_by_api_key[api_key], api_key)


# In[30]:

downloader(search_terms_by_api_key, api_keys)


# In[31]:

for c in db.articles.find()[:3]:
    print(c)


# In[ ]:



