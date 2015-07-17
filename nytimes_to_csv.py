
# coding: utf-8

# #CSV builder for The New York Times

# In[1]:

import math

from blaze import Data, DataFrame
from nltk.tokenize import sent_tokenize
from pymongo import MongoClient
from slugify import slugify


# In[2]:

client = MongoClient()
db = client.nytimes3


# In[3]:

total = db.articles.count()
percent = math.ceil(total / 100)
count = 0
print('Total documents:', total)
print()

total_rows_df = DataFrame()
try:
    for doc in db.articles.find():
        rows_df = DataFrame()
        try:

            # Texts
            common_texts = []
            if doc.get('abstract'):
                common_texts.append(doc['abstract'])
            if doc.get('headline') and isinstance(doc['headline'], dict) and doc['headline'].get('main'):
                common_texts.append(doc['headline']['main'])
            if doc.get('lead_paragraph'):
                common_texts.append(doc['lead_paragraph'])
            # add snippet as variable field

            # Fix fields
            article_id = doc['_id']
            pub_date = doc['pub_date']
            section_name = doc['section_name']
            web_url = doc['web_url']

            # Variable fields
            for term in doc['q_info']:
                texts = list(common_texts)
                q_info = doc['q_info'][term]
                term_category = q_info[0]['term_category']
                search_terms = []
                for info in q_info:
                    search_terms.append(info['q']['term'])
                    if info['snippet']:
                        texts.append(info['snippet'])

                for text in texts:
                    sentences = sent_tokenize(text)
                    for sentence in sentences:
                        if any([slugify(search_term) in slugify(sentence) for search_term in search_terms]):
                            term_aux = term.replace('_', '.')
                            sentence_aux = sentence.replace('<strong>', '').replace('</strong>', '').replace(',', '')
                            if article_id and pub_date and section_name and web_url and term_category and term_aux and sentence_aux:
                                row_df = DataFrame(
                                    [[article_id, pub_date, section_name, web_url, term_category, term_aux, sentence_aux]],
                                    columns=['article_id', 'pub_date', 'section_name', 'web_url', 'term_category', 'term', 'sentence']
                                )
                                rows_df = rows_df.append(row_df)

            total_rows_df = total_rows_df.append(rows_df)

            if count % percent == 0:
                percentage = count // percent
                print('{} out of {} processed.'.format(count, total))
                print('{}% completed.'.format(percentage))
                print()
                total_rows_df.to_csv('total_rows_{}.csv'.format(percentage), index=False)
            count +=1

        except Exception as e:
            print('Error:', e)
            print('Document:', doc)
    
    print('{} out of {} processed.'.format(total, total))
    print('100% completed.')
    total_rows_df.to_csv('total_rows_100.csv', index=False)

except Exception as e:
    print('Error:', e)
    total_rows_df.to_csv('total_rows.csv', index=False)


# In[4]:

# total_rows_df['term'] = total_rows_df['term'].apply(lambda x: x.replace('_', '.'))
# total_rows_df['sentence'] = total_rows_df['sentence'].apply(lambda x: x.replace('<strong>', '').replace('</strong>', ''))
# total_rows_df['sentence'] = total_rows_df['sentence'].apply(lambda x: x.replace(',', '')) # csv delimiter problems


# In[5]:

# total_rows_df.to_csv('total_rows.csv', index=False)


# In[6]:

print(total_rows_df['term'].value_counts())


# In[ ]:



