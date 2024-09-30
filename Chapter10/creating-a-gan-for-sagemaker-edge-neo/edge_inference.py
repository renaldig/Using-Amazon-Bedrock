import numpy as np
import json
import socket
import struct
import matplotlib.pyplot as plt

# Generate a random latent vector
input_data = np.random.randn(1, 100).astype('float32')

# Serialize input data
payload = input_data.tobytes()

# Send data to the agent over Unix socket
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect('/tmp/sagemaker_edge_agent_example.sock')

# Send inference request
request = {
    "model_name": "gan-mnist-model",
    "model_version": "1.0",
    "input_tensor": payload.decode('latin1')  # Decode to handle bytes in JSON
}

request_bytes = json.dumps(request).encode('utf-8')
message_length = struct.pack('I', len(request_bytes))
sock.sendall(message_length + request_bytes)

# Receive response
response_length_bytes = sock.recv(4)
response_length = struct.unpack('I', response_length_bytes)[0]
response_bytes = sock.recv(response_length)
response = json.loads(response_bytes.decode('utf-8'))

# Extract generated image
generated_image = np.array(response['outputs']).reshape(28, 28)

# Display the image
plt.imshow(generated_image, cmap='gray')
plt.title('Generated Image')
plt.axis('off')
plt.show()

# Close the socket connection
sock.close()
