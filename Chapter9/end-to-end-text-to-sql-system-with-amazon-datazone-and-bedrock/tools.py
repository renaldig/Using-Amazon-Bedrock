import json
import boto3
from botocore.client import Config
import time
import logging
import os

# Initialize AWS clients
region = 'us-west-2'
outputLocation = os.environ.get('outputLocation', 's3://<YOUR_OUTPUT_BUCKET_NAME_HERE>/')
kbName = os.environ.get('kbName', 'TextToSQLKB')

datazone = boto3.client('datazone', region_name=region)
athena_client = boto3.client('athena', region_name=region)
glue_client = boto3.client('glue', region_name=region)
bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
bedrock_config = Config(connect_timeout=120, read_timeout=120, retries={'max_attempts': 0})
bedrock_agent_runtime_client = boto3.client("bedrock-agent-runtime", config=bedrock_config, region_name=region)
bedrock_agent_client = boto3.client('bedrock-agent', region_name=region)

# Get Knowledge Base ID
def get_knowledge_base_id():
    paginator = bedrock_agent_client.get_paginator('list_knowledge_bases')
    response_iterator = paginator.paginate()
    for page in response_iterator:
        for kb in page['knowledgeBaseSummaries']:
            if kb['name'] == kbName:
                return kb['knowledgeBaseId']
    return None

knowledge_base_id = get_knowledge_base_id()

def fetch_knowledge_base_references(query_text, model_identifier="anthropic.claude-v2", region_code=region):
    model_arn = f'arn:aws:bedrock:{region_code}::foundation-model/{model_identifier}'

    response = bedrock_agent_runtime_client.retrieve_and_generate(
        input={'text': query_text},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': knowledge_base_id,
                'modelArn': model_arn
            }
        },
    )

    citation_list = response.get("citations", [])
    reference_texts = []
    for citation in citation_list:
        references = citation.get("retrievedReferences", [])
        for ref in references:
            content = ref.get("content", {})
            text = content.get("text", "")
            reference_texts.append(text)

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
    completion_results = response_content.get("completion")
    return completion_results

def fetch_table_schema(database_name):
    try:
        schemas = []

        tables_response = glue_client.get_tables(DatabaseName=database_name)
        table_list = tables_response.get('TableList', [])

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
            QueryExecutionContext={'Database': database_name},
            ResultConfiguration={'OutputLocation': outputLocation}
        )

        query_execution_id = response['QueryExecutionId']

        # Wait for the query to complete
        while True:
            query_status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            status = query_status['QueryExecution']['Status']['State']

            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            time.sleep(2)

        if status == 'SUCCEEDED':
            result = athena_client.get_query_results(QueryExecutionId=query_execution_id)
            return 'SUCCEEDED', result
        else:
            reason = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            return status, reason

    except Exception as error:
        return 'ERROR', f'Error running Athena query: {error}'

def parse_query_results(query_results):
    parsed_data = []
    result_set = query_results.get('ResultSet', {})
    rows = result_set.get('Rows', [])
    columns_metadata = result_set.get('ResultSetMetadata', {}).get('ColumnInfo', [])
    columns = [col['Name'] for col in columns_metadata]

    for row in rows[1:]:  # Skip header row
        data = row.get('Data', [])
        row_data = [field.get('VarCharValue', '') for field in data]
        parsed_data.append(dict(zip(columns, row_data)))

    return parsed_data

def generate_sql(query, sql_error_message="", db="", schema=""):
    details = """It is important that the SQL query complies with Athena (Presto) syntax.
    Use date functions compatible with Athena. For example, use date_add('month', -n, date) to subtract months.
    Ensure that column names and table names are correct."""
    
    if sql_error_message == "":
        prompt = f"""You are an expert SQL assistant. {details}

        Using the following database schema:
        {schema}

        Generate an SQL query for the following question:
        "{query}"

        Respond with only the SQL query and nothing else."""
    else:
        prompt = f"""You are an expert SQL assistant. The previous SQL query resulted in an error: {sql_error_message}
        {details}

        Using the following database schema:
        {schema}

        Generate a corrected SQL query for the following question:
        "{query}"

        Respond with only the SQL query and nothing else."""
    sql = invoke_claude(prompt)
    database = db if db else 'sql-db'
    return database, schema, sql


def run_sql(query):
    database = 'sql-db'  # Replace with your actual database name
    # Fetch the schema from Glue
    schemas = fetch_table_schema(database)
    print(schemas)
    # Construct the schema information string
    schema_info = "\n".join([f"Table {s['Table']}: {s['Schema']}" for s in schemas])

    # Generate the SQL query using the schema
    database, sql_schema, sql = generate_sql(query, schema=schema_info)
    code, sql_results = run_athena_query(database, sql)
    retry_max = 3
    retry_counter = 0

    while code != 'SUCCEEDED' and retry_counter < retry_max:
        sql_error_message = f"Error: {sql_results}"
        database, sql_schema, sql = generate_sql(query, sql_error_message, database, sql_schema)
        code, sql_results = run_athena_query(database, sql)
        retry_counter += 1

    if code == 'SUCCEEDED':
        parsed_results = parse_query_results(sql_results)
        return sql, parsed_results
    else:
        return sql, sql_results
