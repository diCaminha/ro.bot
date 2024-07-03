import os
from openai import OpenAI
from dotenv import load_dotenv
import base64
import numpy as np

from elasticsearch import Elasticsearch

# Elasticsearch setup
es = Elasticsearch([{'host': 'localhost', 'port': 9200, 'scheme': 'http'}])
index_name = 'teses'

# Defina sua chave de API
load_dotenv()
api_key = os.getenv('API_KEY')
client = OpenAI(api_key=api_key)


def search(query, client, es, index_name):
    # Gerar embedding usando o modelo de embeddings da OpenAI
    embedding = client.embeddings.create(
        input=query,
        model="text-embedding-ada-002"
    ).data[0].embedding

    # Converter o embedding para base64
    embedding_b64 = base64.b64encode(np.array(embedding).astype(np.float32).tobytes()).decode('utf-8')

    # Construir a consulta para Elasticsearch
    script_query = {
        "script_score": {
            "query": {"match_all": {}},
            "script": {
                "source": "cosineSimilarity(params.query_vector, doc['embedding']) + 1.0",
                "params": {"query_vector": embedding}
            }
        }
    }

    # Executar a consulta no Elasticsearch
    response = es.search(index=index_name, body={"query": script_query})
    return response


# Exemplo de uso
query = "furto de material de cobre"
response = search(query, client, es, index_name)

# Imprimir a resposta
print(response)