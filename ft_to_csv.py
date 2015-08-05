
# coding: utf-8

# #CSV builder for The Financial Times

# In[1]:

import logging
import math
import os

from blaze import Data, DataFrame
from joblib import Parallel, delayed
from nltk.tokenize import sent_tokenize
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from slugify import slugify


# ##Logging

# In[2]:

try:
    os.remove('ft_to_csv.log')
except:
    pass


# In[3]:

logging.getLogger().handlers = []
logging.getLogger('requests.packages.urllib3').setLevel(logging.WARNING)
logging.basicConfig(filename='ft_to_csv.log', level=logging.INFO, format='%(asctime)s %(message)s')


# In[4]:

def write_log(*args, status=None):
    record = '{} ==> {}'.format(args, status)
    logging.info(record)


# ##MongoDB

# In[5]:

client = MongoClient()
client.drop_database('ft_to_csv')
db = client.ft
db_csv = client.ft_to_csv


# In[6]:

def insert_rows(rows):
    try:
        db_csv.rows.insert_many(rows, ordered=False)
    except Exception as e:
        write_log('DB INSERTION EXCEPTION', status='{}'.format(e))


# In[14]:

total = db.articles.count()
percent = math.ceil(total / 100)
count = 0
print('Total documents:', total)
print()

for doc in db.articles.find():
    rows = []
    try:
        # Texts
        common_texts = []
        if doc.get('title') and isinstance(doc['title'], dict) and doc['title'].get('title'):
            common_texts.append(doc['title']['title'])
        if doc.get('summary') and isinstance(doc['summary'], dict) and doc['summary'].get('excerpt'):
            common_texts.append(doc['summary']['excerpt'])
        # add snippet as variable field NO FOR FT

        # Fix fields
        article_id = doc['_id']
        pub_date = doc['lifecycle']['initialPublishDateTime']
#         section_name = doc['section_name']
        public_url = doc['location']['uri'] # ft
        web_url = doc['apiUrl']

        # Variable fields
        for term in doc['q_info']:
            texts = list(common_texts)
            q_info = doc['q_info'][term]
            term_category = q_info[0]['term_category']
            search_terms = []
            for info in q_info:
                search_terms.append(info['q']['term'])
#                 if info['snippet']:
#                     texts.append(info['snippet'])

            for text in texts:
                sentences = sent_tokenize(text)
                for sentence in sentences:
                    if any([slugify(search_term) in slugify(sentence) for search_term in search_terms]):
                        term_aux = term.replace('_', '.')
#                         sentence_aux = sentence.replace('<strong>', '').replace('</strong>', '').replace(',', '')
                        sentence_aux = sentence
                        if article_id and pub_date and web_url and term_category and term_aux and sentence_aux:
                            row = {
                                'article_id': article_id,
                                'pub_date': pub_date,
#                                 'section_name': section_name,
                                'web_url': web_url,
                                'public_url': public_url, # ft
                                'term_category': term_category,
                                'term': term_aux,
                                'sentence': sentence_aux,
                            }
                            rows.append(row)
        if rows:
            insert_rows(rows)

        if count % percent == 0:
            percentage = count // percent
            print('{} out of {} processed.'.format(count, total))
            print('{}% completed.'.format(percentage))
            print()
        count +=1

    except Exception as e:
        write_log('DOCUMENT {} PROCESS EXCEPTION'.format(doc), status='{}'.format(e))

print('{} out of {} processed.'.format(total, total))
print('100% completed.')


# In[17]:

db_csv.rows.count()


# In[ ]:




# In[ ]:




# In[ ]:



