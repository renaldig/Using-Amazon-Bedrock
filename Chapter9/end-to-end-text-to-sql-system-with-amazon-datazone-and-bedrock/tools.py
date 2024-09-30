# tools.py

import json
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import time
import csv
from io import StringIO
import logging
import os

# Global Configuration
region = os.environ.get("AWS_REGION", "us-east-1")
outputLocation = os.environ.get("ATHENA_OUTPUT_LOCATION", "s3://your-athena-query-results-bucket/")
kbName = os.environ.get("KNOWLEDGE_BASE_NAME", "YourKnowledgeBaseName")

# Initialize AWS Clients
datazone = boto3.client('datazone', region_name=region)
athena_client = boto3.client('athena', region_name=region)
glue_client = boto3.client('glue', region_name=region)

bedrock_runtime = boto3.client(
    service_name="bedrock-runtime",
    region_name=region,
)

bedrock_config = Config(
    connect_timeout=120,
    read_timeout=120,
    retries={'max_attempts': 0}
)

bedrock_agent_runtime_client = boto3.client("bedrock-agent-runtime", config=bedrock_config)
bedrock_agent_client = boto3.client('bedrock-agent')

# Retrieve Knowledge Base ID
knowledge_base_id = ""
paginator = bedrock_agent_client.get_paginator('list_knowledge_bases')
response_iterator = paginator.paginate()
for page in response_iterator:
    for kb in page['knowledgeBaseSummaries']:
        if kb['name'] == kbName:
            knowledge_base_id = kb['knowledgeBaseId']
            break
    if knowledge_base_id:
        break

if not knowledge_base_id:
    raise ValueError(f"Knowledge base with name '{kbName}' not found.")

# Function Definitions

def fetch_knowledge_base_references(query_text, model_identifier="anthropic.claude-v2", region_code=region):
    model_arn = f'arn:aws:bedrock:{region_code}::foundation-model/{model_identifier}'

    response = bedrock_agent_runtime_client.retrieve_and_generate(
        input={
            'text': query_text
        },
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': knowledge_base_id,
                'modelArn': model_arn
            }
        },
    )

    print(f'Knowledge base search response: {response}')

    citation_list = response.get("citations", [])
    reference_texts = []
    for citation in citation_list:
        references = citation.get("retrievedReferences", [])
        for ref in references:
            reference_texts.append(ref["content"].get("text", ""))

    return reference_texts

def format_claude_prompt(prompt_text: str) -> str:
    return f"\n\nHuman: {prompt_text}\n\nAssistant:"

def invoke_claude(prompt_text):
    # Configuration for the prompt
    prompt_settings = {
        "prompt": format_claude_prompt(prompt_text),
        "max_tokens_to_sample": 4096,
        "temperature": 0,
        "top_k": 250,
        "top_p": 0.999,
        "stop_sequences": [],
    }

    # Convert the configuration to a JSON string
    request_body = json.dumps(prompt_settings)

    model_id = "anthropic.claude-v2"
    accept_format = "application/json"
    content_type = "application/json"

    response = bedrock_runtime.invoke_model(
        body=request_body, modelId=model_id, accept=accept_format, contentType=content_type
    )
    
    response_content = json.loads(response.get("body").read())
    completion_results = response_content.get("completion", "")
    return completion_results.strip()

def invoke_titan_model(prompt_text):
    generation_config = {
        "inputText": prompt_text,
        "textGenerationConfig": {
            "maxTokenCount": 4096,
            "stopSequences": [],
            "temperature": 0.7,
            "topP": 1,
        },
    }

    request_body = json.dumps(generation_config)
    model_id = "amazon.titan-text-lite-v1"
    accept_format = "application/json"
    content_type = "application/json"

    response = bedrock_runtime.invoke_model(
        body=request_body, modelId=model_id, accept=accept_format, contentType=content_type
    )

    response_content = json.loads(response.get("body").read())
    generated_text = response_content.get("results")[0].get("outputText", "")
    return generated_text.strip()

def fetch_table_schema(database_name):
    try:
        schemas = []

        tables_response = glue_client.get_tables(DatabaseName=database_name)
        table_list = tables_response['TableList']

        for table in table_list:
            table_name = table['Name']
            columns = table['StorageDescriptor']['Columns']
            schema = {column['Name']: column['Type'] for column in columns}
            schemas.append({"Table": table_name, "Schema": schema})

        return schemas

    except Exception as error:
        print(f"Error fetching table schema: {error}")
        return []

def run_athena_query(database_name, query_string):
    try:
        response = athena_client.start_query_execution(
            QueryString=query_string,
            QueryExecutionContext={
                'Database': database_name
            },
            ResultConfiguration={
                'OutputLocation': outputLocation
            }
        )
        
        query_execution_id = response['QueryExecutionId']
        print(f"Query Execution ID: {query_execution_id}")

        # Wait for the query to complete
        while True:
            query_status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            query_state = query_status['QueryExecution']['Status']['State']

            if query_state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            else:
                print("Query is still running...")
                time.sleep(2)
        
        if query_state == 'SUCCEEDED':
            print("Query succeeded!")

            query_result = athena_client.get_query_results(QueryExecutionId=query_execution_id)
            result_data = parse_query_results(query_result)
            return 'SUCCEEDED', result_data
        else:
            print("Query failed!")
            status_message = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
            return 'FAILED', status_message

    except Exception as error:
        status_message = f'Error: {error}'
        return 'ERROR', status_message

def parse_query_results(query_results):
    parsed_data = []
    result_set = query_results.get('ResultSet', {})
    rows = result_set.get('Rows', [])
    if not rows:
        return parsed_data

    # Extract column names from the first row
    columns_metadata = result_set.get('ResultSetMetadata', {}).get('ColumnInfo', [])
    columns = [col['Name'] for col in columns_metadata]

    # Skip the header row
    for row in rows[1:]:
        data = row.get('Data', [])
        row_data = [field.get('VarCharValue', '') for field in data]
        parsed_data.append(dict(zip(columns, row_data)))

    return parsed_data

def generate_sql(query, sqlerrormessage="", db="", schema=""):
    table_information = ""

    if sqlerrormessage == "":
        prompt = f"""Extract main entities and metrics from the below question.
Question: "{query}"
Respond only with the entities and metrics and nothing else."""
        entities = invoke_claude(prompt)
        print(f'Entities: {entities}')
        knowledge_base_prompt = f'List all table schema(s) that are relevant to {entities}'
        datasets = fetch_knowledge_base_references(knowledge_base_prompt)
        print(f'Datasets: {datasets}')
        if not datasets:
            return "", "", f"No datasets identified in knowledge base for entities: {entities}"
        else:
            for dataset in datasets:
                dataset_info = json.loads(dataset)
                table_arn = dataset_info.get("glue_table_arn", "")
                table_name = dataset_info.get("name", "")
                table_information += f"\nTable ARN: {table_arn}\n"
                table_information += f"Table Name: {table_name}\n"
                table_information += f"Table Columns:\n"

                # Process business columns
                business_columns = dataset_info.get("glue_table_business_columns", "")
                if business_columns:
                    try:
                        business_columns_json = json.loads(business_columns)
                    except Exception as e:
                        print(f'Error parsing business columns: {e}')
                        business_columns_json = []
                else:
                    business_columns_json = []

                # Process technical columns
                technical_columns = dataset_info.get("glue_table_columns", "")
                if technical_columns:
                    try:
                        technical_columns_json = json.loads(technical_columns)
                    except Exception as e:
                        print(f'Error parsing technical columns: {e}')
                        technical_columns_json = []
                else:
                    technical_columns_json = []

                if business_columns_json:
                    for tech_col, biz_col in zip(technical_columns_json, business_columns_json):
                        column_name = tech_col.get("columnName", "")
                        data_type = tech_col.get("dataType", "")
                        description = biz_col.get("description", "")
                        table_information += f"{column_name} {data_type}, -- {description}\n"
                else:
                    for tech_col in technical_columns_json:
                        column_name = tech_col.get("columnName", "")
                        data_type = tech_col.get("dataType", "")
                        table_information += f"{column_name} {data_type},\n"

                # Extract database name from table ARN
                try:
                    database = table_arn.split(":")[-1].split("/")[1]
                except Exception as e:
                    print(f'Error extracting database name: {e}')
                    database = ""

            sql_schema = table_information

    else:
        database = db
        sql_schema = schema

    details = """It is important that the SQL query complies with Athena syntax.
- Use aliases if column names are the same during joins, e.g., llm.customer_id in SELECT statement.
- Enclose string values in quotes.
- Include all required columns when writing CTEs.
- Cast non-string columns to string when concatenating."""

    if sqlerrormessage != "":
        prompt = f"""You are a SQL expert. Review the error: {sqlerrormessage}.
{details}
Generate a SQL statement for the following question:
"{query}"
Using the below SQL schema:
{sql_schema}
Respond with only the SQL and nothing else."""
    else:
        prompt = f"""You are a SQL expert.
{details}
Generate a SQL statement for the following question:
"{query}"
Using the below SQL schema:
{sql_schema}
Respond with only the SQL and nothing else."""

    sql = invoke_claude(prompt)
    return database, sql_schema, sql

def execute_athena_query(database, sql):
    print(f'Executing SQL: {sql}')
    code, results = run_athena_query(database, sql)
    return code, results

def run_sql(query):
    print(f'Running SQL for query: {query}')
    database, sql_schema, sql = generate_sql(query)
    if not sql:
        return sql, sql_schema  # Return error message if SQL generation failed

    print(f'Database: {database}')
    print(f'Generated SQL Schema: {sql_schema}')
    print(f'Generated SQL: {sql}')

    code, sql_results = execute_athena_query(database, sql)
    retry_max = 3
    retry_counter = 0

    while True:
        if code != 'SUCCEEDED':
            sqlerrormessage = f'Generated SQL query: {sql} produced the following error: {sql_results}'
            print(sqlerrormessage)
            database, sql_schema, sql = generate_sql(query, sqlerrormessage, database, sql_schema)
            if not sql:
                return sql, sql_schema  # Return error message if SQL regeneration failed

            print(f'Database: {database}')
            print(f'Generated SQL Schema: {sql_schema}')
            print(f'Generated SQL: {sql}')
            code, sql_results = execute_athena_query(database, sql)

            retry_counter += 1
            if code == 'SUCCEEDED' or retry_counter >= retry_max:
                break
            print(f'Retry Counter: {retry_counter}')
        else:
            break

    return sql, sql_results
