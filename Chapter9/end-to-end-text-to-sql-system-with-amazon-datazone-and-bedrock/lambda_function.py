# lambda_function.py

import tools
import os
import logging

def handler(event, context):
    response_code = None

    # Data Extraction from Event
    action = event.get("actionGroup", "")
    api_path = event.get("apiPath", "")
    parameters = event.get("parameters", {})
    httpMethod = event.get("httpMethod", "")

    # Main Logic Based on API Path
    if api_path == "/run_sql":
        query = parameters.get("query", "")
        if not query:
            response_body = {"application/json": {"body": {"error": "No query provided"}}}
            response_code = 400
        else:
            sql, sql_results = tools.run_sql(query)
            response_body = {
                "application/json": {
                    "body": {
                        "generated_sql_query": str(sql),
                        "sql_query_results": str(sql_results),
                    }
                }
            }
            response_code = 200
    else:
        body = f"{action}::{api_path} is not a valid API, try another one."
        response_code = 400
        response_body = {"application/json": {"body": {"error": body}}}

    # Compile Response and Return
    action_response = {
        "actionGroup": action,
        "apiPath": api_path,
        "httpMethod": httpMethod,
        "httpStatusCode": response_code,
        "responseBody": response_body,
    }
    api_response = {"messageVersion": "1.0", "response": action_response}
    return api_response
