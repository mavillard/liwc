
# coding: utf-8

# #Sentence extractor for The New York Times

# In[2]:

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

# In[3]:

try:
    os.remove('search4.log')
except:
    pass


# In[4]:

logging.getLogger().handlers = []
logging.getLogger('requests.packages.urllib3').setLevel(logging.WARNING)
logging.basicConfig(filename='search4.log', level=logging.INFO, format='%(asctime)s %(message)s')


# In[5]:

def write_log(*args, status=None):
    record = '{} ==> {}'.format(args, status)
    logging.info(record)


# ##MongoDB

# In[6]:

client = MongoClient()
client.drop_database('nytimes4')
db = client.nytimes4


# In[7]:

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

# In[8]:

# def preprocess_term(term):
#     terms = []
    
#     curated_term = term.lower()
#     curated_term = curated_term.replace(' & ', ' ')
#     curated_term = curated_term.replace(' and ', ' ')
#     terms.append(curated_term)
#     if '-' in curated_term:
#         terms.append(curated_term.replace('-', ''))
# #         terms.append(curated_term.replace('-', ' ')) # same result

#     for term in terms:
#         if term.endswith('corporation'):
#             terms.append(term[:-12])
#         elif term.endswith('corp'):
#             terms.append(term[:-5])
#         elif term.endswith('company'):
#             terms.append(term[:-8])
#         elif term.endswith('inc.'):
#             terms.append(term[:-5])
#         elif term.endswith('inc'):
#             terms.append(term[:-4])
#         elif term.endswith('.com'):
#             terms.append(term[:-4])
    
# #     terms = list(map(lambda x: '"{}"'.format(x), terms))
#     return terms


# In[9]:

# term_dict = {}
# for i in range(1, 4):
#     term_dict[i] = {}
#     st_file = open('search_terms_{}.txt'.format(i))
#     term_list = map(lambda x: x.strip(), st_file.readlines())
#     for term in term_list:
#         term_dict[i][term] = preprocess_term(term)


# In[10]:

# with open('search_terms.yml', 'w') as search_term_file:
#     search_term_file.write(yaml.dump(term_dict, default_flow_style=False))


# In[11]:

with open('search_terms_4.yml') as search_term_file:
    term_yaml = yaml.load(search_term_file.read())
    #
    for key in term_yaml:
        d = term_yaml[key]
        for k in d:
            d[k] = list(map(lambda x: '"{}"'.format(x), d[k]))


# ##NYTimes API keys

# In[12]:

# One API key for each of the cores
api_keys = [
#     "3439a9084efa80c4f5fb1d290dfc1b44:11:70233981", # my api key
#     "a5c709f3168b829711241b243457e9d6:13:70235641", # the other api key
    "c7ba2eac72924572152e63f4516210d7:14:72380734", # my second api key
    "7e692d35c7bd20618395859a3c4cbef6:15:72380785", # my third api key
    "ba47374fd391c9bc5fd3ca51ff953a44:14:70229228",
#     "4557e02788189abb3642a33bca7469ff:11:69136863",
#     "2b3d39fd4c7836168a2a370c25ad6232:16:70235576",
#     "87d7b22c0feec4f3112d80b71d0b500a:1:69642501",
#     "d7655429355ab2df4621a10c01d04865:8:69135199",
#     "1944df13b86dd83e4a8c4ea82e767975:2:65092848",
#     "730e30f5220059551e666430644fbf87:11:69642501", # developer inactive
]


# In[13]:

def next_multiple(n, m):
    # 4, 17 ==> 20
    rest = m % n
    return m if rest == 0 else m + n - rest

def chunks(l, n_chunks):
    l = list(l)
    size = len(l)
    n = next_multiple(n_chunks, size) // n_chunks
    for i in range(0, size, n):
        yield l[i:i + n]


# In[14]:

# [(search_term, original_term, term_type)]
search_terms = [(t, k2, k1)
                   for k1 in term_yaml
                       for k2 in term_yaml[k1]
                           for t in term_yaml[k1][k2]
              ]


# In[15]:

# # TEST

# api_keys = [
#     "3439a9084efa80c4f5fb1d290dfc1b44:11:70233981", # my api key
#     "a5c709f3168b829711241b243457e9d6:13:70235641", # the other api key
# ]

# search_terms = [
#     ('"entrepreneur"', 'entrepreneur', 1),
#     ('"executive"', 'executive', 1),
#     ('"google"', 'google', 2),
#     ('"amazon"', 'amazon.com', 2),
#     ('"amazon.com"', 'amazon.com', 3),
#     ('"ebay"', 'e-bay', 3),
# #     ('"facebook"', 'facebook', 3),
# ]

# BEGIN_DATE = date(2014, 1, 1)
# END_DATE = date(2014, 2, 28)


# In[16]:

search_terms


# In[17]:

search_terms_by_api_key = defaultdict(list)
for i in range(2, 4):
    search_terms_i = list(filter(lambda x: x[2] == i, search_terms))
    for t in zip(api_keys, chunks(search_terms_i, len(api_keys))):
        search_terms_by_api_key[t[0]].extend(t[1])


# ##Dates

# In[18]:

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
        yield (aux_date, min(aux_date + timedelta(ndays), end_date))
        aux_date += timedelta(ndays + 1)


# ##Timer

# In[19]:

LAST_REQUEST = time()


# In[20]:

def wait(f, *args, t=9):
    global LAST_REQUEST
    now = time()
    elapsed_time = now - LAST_REQUEST
    if elapsed_time < t:
        sleep(t - elapsed_time)
    LAST_REQUEST = time()
    return f(*args)


# ##Query

# In[21]:

class Query:
    def __init__(self, term, begin_date, end_date, page, api_key):
        self.term = term
        self.begin_date = begin_date
        self.end_date = end_date
        self.page = page
        self.api_key =api_key
    
    def __repr__(self):
        return 'Q<{}, {}, {}, {}, {}>'.format(self.term, self.begin_date, self.end_date, self.page, self.api_key)


# ##Downloader

# In[22]:

BEGIN_DATE = date(1999, 1, 1)
END_DATE = date(2014, 12, 31)


# In[23]:

def search(q):
    try:
        base_url = 'http://api.nytimes.com/svc/search/v2/articlesearch.json'
        payload = {'q': q.term, 'begin_date': q.begin_date, 'end_date': q.end_date, 'page': q.page, 'api-key': q.api_key}
        fl = [
            'web_url', 'snippet', 'lead_paragraph', 'abstract', 'source', 'headline',
            'keywords', 'pub_date', 'document_type', 'section_name', '_id',
        ]
        payload.update({'sort': 'oldest', 'fq': 'source:("The New York Times")', 'fl': ','.join(fl), 'hl': 'true'})
        r = requests.get(base_url, params=payload)
        response = r.json()
        
        if response['status'] == 'OK':
            write_log(q, status='SEARCH OK {}'.format(response['response']['meta']['hits']))
        elif response['status'] == 'ERROR':
            write_log(q, status='SEARCH ERROR {}'.format(response['errors']))
        else:
            write_log(q, status='SEARCH {}'.format(response['status']))
    except ValueError as e:
        if str(e) == 'Expecting value: line 1 column 1 (char 0)':
            write_log(q, status='SEARCH ERROR api-key')
        else:
            write_log(q, status='SEARCH EXCEPTION {}'.format(e))
        response = {'status': 'ERROR'}
    except Exception as e:
        write_log(q, status='SEARCH EXCEPTION {}'.format(e))
        response = {'status': 'ERROR'}
    return response


# In[24]:

def get_documents_by_page(q, term, total_results):
    n_pages = math.ceil(total_results / 10)
    for page in range(n_pages):
        q.page = page
        response = wait(search, q)
        
        if response['status'] == 'OK':
            docs = response['response']['docs']
            for doc in docs:
                snippet = doc['snippet']
                orig_term = term[1].replace('.', '_')
                doc.update({'q_info': {orig_term: [{'q': q.__dict__, 'term_category': term[2], 'snippet': snippet}]}})
                del(doc['snippet'])
            insert_documents(docs, q)


# In[25]:

def get_documents_by_query(q, term):
    response = wait(search, q)
    
    if response['status'] == 'OK':
        total_results = response['response']['meta']['hits']
        if total_results <= 1010:
            get_documents_by_page(q, term, total_results)
        else:
            bd = parser.parse(q.begin_date)
            ed = parser.parse(q.end_date)
            half = (ed - bd) // 2
            
            begin_date1 = q.begin_date
            end_date1 = (bd + timedelta(half.days)).strftime("%Y%m%d")
            q1 = Query(q.term, begin_date1, end_date1, 0, q.api_key)
            get_documents_by_query(q1, term)
            
            begin_date2 = (bd + timedelta(half.days + 1)).strftime("%Y%m%d")
            end_date2 = q.end_date
            q2 = Query(q.term, begin_date2, end_date2, 0, q.api_key)
            get_documents_by_query(q2, term)


# In[26]:

def download_by_date_ranges(term, api_key):
    for r in date_ranges(BEGIN_DATE, END_DATE, 1):
        begin_date = r[0].strftime("%Y%m%d")
        end_date = r[1].strftime("%Y%m%d")
        q = Query(term[0], begin_date, end_date, 0, api_key)
        get_documents_by_query(q, term)


# In[27]:

def download_by_term(term, api_key):
    begin_date = BEGIN_DATE.strftime("%Y%m%d")
    end_date = END_DATE.strftime("%Y%m%d")
    q = Query(term[0], begin_date, end_date, 0, api_key)
    response = wait(search, q)
    
    if response['status'] == 'OK':
        total_results = response['response']['meta']['hits']
        if total_results <= 1010:
            get_documents_by_page(q, term, total_results)
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
    Parallel(n_jobs=3)(delayed(download_by_key)(search_terms_by_api_key[api_key], api_key) for api_key in api_keys)

    # Version sequencial
#     for api_key in api_keys:
#         download_by_key(search_terms_by_api_key[api_key], api_key)


# In[30]:

downloader(search_terms_by_api_key, api_keys)


# In[31]:

# for d in db.articles.find():
#     if len(d['q_info']) > 1:
#         k = list(d['q_info'].keys())[0]
#         if len(d['q_info'][k]) > 1:
#             print(d['_id'])
#             print(d['q_info'])
#             break

# 52c8a3eb38f0d862ec32236f
# {
# 'amazon_com': [{
#     'q': {'page': 0, 'end_date': '20140228', 'term': '"amazon.com"', 'begin_date': '20140101', 'api_key': '3439a9084efa80c4f5fb1d290dfc1b44:11:70233981'},
#     'term_category': 3,
#     'snippet': 'Jeff Bezos, vacationing in the Galapagos Islands this week, felt some serious pain. And it wasn’t just because UPS had failed to make all of Amazon’s shipments by Christmas.'
#     }, {
#     'q': {'page': 0, 'begin_date': '20140101', 'end_date': '20140228', 'term': '"amazon"', 'api_key': 'a5c709f3168b829711241b243457e9d6:13:70235641'},
#     'term_category': 2,
#     'snippet': 'The Ecuadorean Navy offered Jeff Bezos same-day shipping on an <strong>Amazon</strong> Prime package: Mr. Bezos himself. Amazon’s chief executive suffered a kidney stone attack visiting the Galapagos Islands this week, according to the local'
#     }],
# 'executive': [{
#     'q': {'page': 10, 'end_date': '20140116', 'term': '"executive"', 'begin_date': '20140101', 'api_key': 'a5c709f3168b829711241b243457e9d6:13:70235641'},
#     'term_category': 1,
#     'snippet': 'The Ecuadorean Navy offered Jeff Bezos same-day shipping on an Amazon Prime package: Mr. Bezos himself. Amazon’s chief <strong>executive</strong> suffered a kidney stone attack visiting the Galapagos Islands this week, according to the local'
#     }]
# }


# In[32]:

# db.articles.find_one({'_id':'52c8a3eb38f0d862ec32236f'})


# In[33]:

db.articles.count()


# In[34]:

for d in db.articles.find()[:1]:
    print(d)


# In[35]:

d


# In[ ]:



