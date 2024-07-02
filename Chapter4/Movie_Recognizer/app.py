import gradio as gr

import boto3
import json
import base64
from botocore.config import Config

import requests
from requests.auth import HTTPBasicAuth

elastic_url = "https://127.0.0.1:9200"
user = "admin"
passwd = "<YOUR_PASSWORD_HERE>"

requests.packages.urllib3.disable_warnings()

boto_cfg = Config(
    region_name='us-west-2',
    signature_version='v4',
    retries={'max_attempts': 10, 'mode': 'standard'}
)

bedrock_client = boto3.client(service_name="bedrock", config=boto_cfg)
runtime_client = boto3.client(service_name="bedrock-runtime", config=boto_cfg)

def fetch_text_embedding(text_input):
    payload = json.dumps({"inputText": text_input})

    response = runtime_client.invoke_model(
        body=payload,
        modelId="amazon.titan-embed-image-v1",
        accept="application/json",
        contentType="application/json"
    )

    response_data = json.loads(response['body'].read().decode('utf8'))
    return response_data, text_input

def format_result_html(result_hit):
    image_path = "images/" + result_hit['_source']['posterPath']
    with open(image_path, 'rb') as img_file:
        encoded_image = base64.b64encode(img_file.read()).decode('utf-8').replace('\n', '')

    html_template = f"""
    <div style="display: flex; flex-direction: row; align-items: center; margin-bottom: 10px;">
        <img src="data:image/png;base64,{encoded_image}" style="width: 150px; height: 225px; margin-right: 10px;"/>
        <div style="display: flex; flex-direction: column; justify-content: space-between;">
            <div style="display: flex; flex-direction: row; align-items: center; justify-content: space-between;">
                <div style="font-size: 20px; font-weight: bold; margin-right: 10px;">{result_hit['_source']['title']}</div>
                <div style="font-size: 20px; font-weight: bold; margin-right: 10px;">{result_hit['_score']}</div>
            </div>
            <div style="font-size: 15px;">{result_hit['_source']['plotSummary']}</div>
        </div>
    </div>
    """
    return html_template

def perform_query(input_text, num_results=1):
    text_embedding, _ = fetch_text_embedding(input_text)

    search_query = {
        "size": num_results,
        "query": {
            "knn": {
                "titan_multimodal_embedding": {
                    "vector": text_embedding[0]['embedding'],
                    "k": num_results
                }
            }
        },
        "_source": ["movieId", "title", "imdbMovieId", "posterPath", "plotSummary"]
    }

    search_response = requests.get(
        f"{elastic_url}/multi-modal-embedding-index/_search",
        auth=HTTPBasicAuth(user, passwd),
        verify=False,
        json=search_query
    )

    search_results = search_response.json()
    html_output = ""
    for hit in search_results['hits']['hits']:
        html_output += format_result_html(hit)

    return html_output

input_box = gr.Textbox(lines=2, label="Input Text")
output_display = gr.HTML(label="Results")

interface_title = "Movie Search"
interface_description = "Search for movies based on title or a description of the movie poster."

app_interface = gr.Interface(
    fn=perform_query,
    inputs=input_box,
    outputs=output_display,
    title=interface_title,
    description=interface_description
)

if __name__ == "__main__":
    app_interface.launch()
