from flask import Flask, request, jsonify, render_template
import boto3
import os
from langchain.memory import ConversationBufferMemory
from langchain.llms.bedrock import Bedrock
from langchain.chains import ConversationChain

app = Flask(__name__)

bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name='us-west-2'
)

context = ConversationBufferMemory()
context.chat_memory.add_user_message("You are an AI that provides food suggestions based on preferences. Generate your own opinions and answer in a personalized way.")
context.chat_memory.add_ai_message("I am an AI that provides food suggestions based on preferences. I will generate my own opinions when asked about food and answer in a personalized way. I will be opinionated.")

ai21_llm = Bedrock(model_id="ai21.j2-ultra", client=bedrock_runtime)
ai21_llm.model_kwargs = {"maxTokens": 500, 'temperature': 1.0, 'topP': 0.9}
conversation = ConversationChain(
     llm=ai21_llm, verbose=True, memory=context
)

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/suggest_food', methods=['POST'])
def suggest_food():
    user_input = request.form.get('user_input', '')
    conversation.verbose = True
    response = conversation.predict(input=user_input)
    return jsonify({"response": response})

if __name__ == '__main__':
    app.run(debug=True)
