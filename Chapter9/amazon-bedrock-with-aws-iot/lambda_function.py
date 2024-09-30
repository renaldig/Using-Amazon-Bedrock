import json
import boto3

def lambda_handler(event, context):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('EnvironmentalData')

    # Scan the table and get all entries
    response = table.scan()
    data = response['Items']

    # Sort data by Timestamp descending
    data.sort(key=lambda x: x['Timestamp'], reverse=True)
    latest_data = data[:10]

    # Calculate averages
    avg_temp = sum(float(item['Temperature']) for item in latest_data) / len(latest_data)
    avg_humidity = sum(float(item['Humidity']) for item in latest_data) / len(latest_data)
    avg_co2 = sum(float(item['CO2']) for item in latest_data) / len(latest_data)

    averages = {
        'AverageTemperature': round(avg_temp, 2),
        'AverageHumidity': round(avg_humidity, 2),
        'AverageCO2': round(avg_co2, 2)
    }

    # Prepare input for the model
    input_text = (
        f"Provide insights based on the following environmental averages:\n"
        f"Temperature: {averages['AverageTemperature']}°C\n"
        f"Humidity: {averages['AverageHumidity']}%\n"
        f"CO2 Levels: {averages['AverageCO2']} ppm\n"
    )

    # Initialize Bedrock client
    bedrock = boto3.client('bedrock')

    # Call the model (replace 'amazon.titan-text' with the actual model ID if different)
    response = bedrock.invoke_model(
        modelId='amazon.titan-text',  # Example model ID
        contentType='text/plain',
        accept='text/plain',
        body=input_text
    )

    # Get the model's output
    model_output = response['body'].read().decode('utf-8')

    return {
        'statusCode': 200,
        'body': json.dumps({
            'Averages': averages,
            'Insights': model_output
        })
    }
