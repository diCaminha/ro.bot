from elasticsearch import Elasticsearch, helpers

# Connect to Elasticsearch
es = Elasticsearch([{'host': 'localhost', 'port': 9200, 'scheme': 'http'}])

# Specify the index name
index_name = 'teses'

# Check if the index exists before deleting
if es.indices.exists(index=index_name):
    # Delete the index
    es.indices.delete(index=index_name)
    print(f"Index '{index_name}' deleted.")
else:
    print(f"Index '{index_name}' does not exist.")