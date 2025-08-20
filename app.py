from flask import Flask, request, jsonify
from Lex_Lang_Graph import app  # This imports the compiled 'app' from your agent.py file

# 1. Create the Flask web server application
server = Flask(__name__)

@server.route("/")
def heartbeat():
    """A simple route to check if the server is running."""
    return "Agent server is alive!"

# 2. Define the 'hotline' or 'endpoint' for your agent
@server.route("/invoke", methods=["POST"])
def invoke_agent():
    print("--- SERVER: A request just arrived at the /invoke door! ---")
    
    # This is the real agent logic
    data = request.get_json()
    task = data["task"]
    result = app.invoke({"task": task})
    print(f"--- SERVER: The agent has given it's answer {result} ---")
    final_answer = result.get("result", 'No result found.')  # 
    return jsonify({"response": final_answer})

# 3. Start the server when you run this file
if __name__ == "__main__":
    print("Starting the agent's server...")
    # The pre-warming is removed. The server will start instantly.
    print("The agent is now 'on call' and listening for tasks from the GUI.")
    server.run(host="127.0.0.1", port=8080)