import tools
import os

def lambda_handler(event, context):
    response_code = None

    action = event.get("actionGroup", "")
    api_path = event.get("apiPath", "")
    parameters = event.get("parameters", {})
    httpMethod = event.get("httpMethod", "")

    if api_path == "/run_sql":
        query = parameters.get('query', '')
        sql, sql_results = tools.run_sql(query)
        response_body = {"application/json": {"body": {"generated_sql_query": str(sql), "sql_query_results": str(sql_results)}}}
        response_code = 200
    else:
        body = {"{}::{} is not a valid api, try another one.".format(action, api_path)}
        response_code = 400
        response_body = {"application/json": {"body": str(body)}}

    action_response = {
        "actionGroup": action,
        "apiPath": api_path,
        "httpMethod": httpMethod,
        "httpStatusCode": response_code,
        "responseBody": response_body,
    }
    api_response = {"messageVersion": "1.0", "response": action_response}
    return api_response
