from typing import TypedDict
from langgraph.graph import StateGraph , END
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_experimental.tools import PythonREPLTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.utilities import SerpAPIWrapper
import subprocess
import json
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import datetime
from pathlib import Path
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

with  open("C:\\Users\\aksha\\Downloads\\coding.txt", "r", encoding="utf-8") as f:
    coding_prompt = f.read()

with  open("C:\\Users\\aksha\\Downloads\\casual.txt", "r", encoding="utf-8") as f:
    casual_prompt = f.read()

serpapi_tool = SerpAPIWrapper(
    serpapi_api_key="4fc549ec74388e04d22853e6a69abdd405d682d78b1a9d2728b129bf92959dac"
)


Index_Path = Path("C:\\Users\\aksha\\V3\\index")
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
if Index_Path.exists():
    print("Loading existing index...")
    vector_store = FAISS.load_local(str(Index_Path), embedding_model , allow_dangerous_deserialization=True)
else:
    print("No FAISS index found. Creating a new one.")
    # FAISS can't be empty, so we start it with a dummy document.
    initial_doc = Document(page_content = "This is the beginning of the agent's memory.")
    vector_store = FAISS.from_documents([initial_doc], embedding_model)
    vector_store.save_local(Index_Path)
retriever = vector_store.as_retriever()


now = datetime.datetime.now()

current_time = now.strftime("%Y-%m-%d %H:%M:%S")

llm = ChatGroq(
    model_name="Llama3-70b-8192",
    groq_api_key="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",
    temperature=0.1,  
    max_tokens=6000,  
) 


Python_repl = PythonREPLTool()

class GraphState(TypedDict): # Here we define the state of the graph, which will be passed between nodes.
    task : str
    result : str # result from the coding node or parent node
    decision : str # desicion made by the router
    notes : str # notes from the serpapi tool
    error_report : str # error report from the child node
    code : str # code from the coding node
    memory : str # memory from the memory node

   
def router(state : GraphState):
    prompt = ChatPromptTemplate( [ ("system" , """You are called as a Router from now on, A Part of a multi Agentic System. Your job is to route tasks.
                The tasks you revieve could be considered two types, either Casual(Ex : Only Conversations and information) or Coding(Interacting with PC, opening apps, anything that ins't a conversation) type of tasks. Only Reply with a single word, 
                 either coding or casual, that Is all.""") , ("user", "{task}")])
    decision_Chain = prompt | llm | StrOutputParser()
    result = decision_Chain.invoke({"task" : state["task"]}) # there is a word task in the graph state, which is the task that is being passed to the router.
    return {"decision" : result.strip()}





def run_shell_command(command: str) -> str:
    """A simple function to run a command in the terminal."""
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"

available_tools = {"run_shell_command": run_shell_command}

def casual_node(state : GraphState):
    print("Casual Agent Activated")
    notes = serpapi_tool.run(state["task"])
    print("Notes from SerpAPI has been recieved")
    prompt_casual = ChatPromptTemplate.from_messages([
        ("system" , casual_prompt), ("user" , "{task}\n\n{notes}\n\n{memory}")
    ])
    casual_memory = state.get("memory", "") # Get the memory from the state
    print("Revising the memory...")
    chain = prompt_casual | llm | StrOutputParser()
    Response = chain.invoke({"task" : state["task"] , "notes" : notes , "memory" : casual_memory})
    return {"result" : Response}


def coding_node(state : GraphState):
    print("Coding Agent Activated!")

    error_report = state.get("error_report", "")
    if error_report:
        print("Error Report from Child Node:", error_report)
        state["task"] += f"\n\nPlease fix the following errors:\n{error_report}"

    prompt_coding = ChatPromptTemplate.from_messages([
        ("system" , coding_prompt)
         , ("user" , "{task}")
    ])
    notes = serpapi_tool.run(state["task"])
    chain = prompt_coding | llm | StrOutputParser()
    dictionary = {"task" : state["task"], "note" : notes}
    Response_of_code = chain.invoke(dictionary)
    return { "code" : Response_of_code}


def parent_node(state: GraphState):
    print("Parent Node Activated...Executing the Code prvided by the coding agent")
    prompt_parent = ChatPromptTemplate.from_messages([
        ("system", """You are a parent node in a multi Agentic System, Your only task is to execute the code provided by the coding agent, and return the result of the code execution.""")
    ])
    code = Python_repl.run(state["code"], globals=available_tools)
    return {"result": code.strip()}


def child_node(state: GraphState):
    print("Child Node Activated...Checking for errors in the code provided by the coding agent")
    prompt_child = ChatPromptTemplate.from_messages([
        ("system" , """you are a agent in a multi Agentic System, You're only task is to check the code provided  for errors, and if there are any errors, you must Point out the errors and send them back.""")
    ])
    child_chain = prompt_child | llm | StrOutputParser()
    error_check = child_chain.invoke({"task": state["result"]})
    return {"error_report": error_check.strip()}


def memory(state: GraphState): # this node is used to update the memory file with the current state of the graph.
    memory_log = {"task" : state.get("task", ""),
              "result" : state.get("result", ""),   
              "decision" : state.get("decision", ""),
              "notes" : state.get("notes", ""),
              "error_report" : state.get("error_report", ""),
              "code" : state.get("code", "")}
    memory_content = json.dumps(memory_log, indent=4)
    with open("C:\\Users\\aksha\\V3\\memory_lex.txt", "a") as f:
         f.write( json.dumps(f"{current_time} {memory_log} ") + "\n")
    
    try :

         docs = Document(page_content=memory_content)
         vector_store.add_documents([docs])  # Add the new memory content to the vector store
         vector_store.save_local(Index_Path)  # Save the updated vector store
    except Exception as e:
         print(f"Error updating memory: {e}")
    return {}
    



def get_memory(state: GraphState): # this simply retrieves the memory from the file and returns it.
    query= (state["task"])

    docs = retriever.invoke(query) # Use the retriever to get relevant documents based on the query
    if docs :
       context = "\n".join([doc.page_content for doc in docs])  # Join the content of the retrieved documents
       return {"memory": context}  
    else:   
        retrieved_context = "No relevant memory found."
    
    # return it as a dictionary to update the "memory" field in the state
    return {"memory": retrieved_context}
    



workflow = StateGraph(GraphState)

workflow.add_node("casual", casual_node)
workflow.add_node("coding", coding_node)
workflow.add_node("parent", parent_node)
workflow.add_node("child", child_node)
workflow.add_node("router", router)
workflow.add_node("Memory", memory)
workflow.add_node("get_memory", get_memory)

workflow.set_entry_point("router")
workflow.add_conditional_edges(
    "router",
    lambda state: state["decision"],
    {
        "casual": "get_memory",
        "coding": "get_memory",
    }
)

workflow.add_conditional_edges(
    "get_memory",
    lambda state: state["decision"],
    {
        "casual": "casual",
        "coding": "coding",
    }
)


workflow.set_finish_point("Memory")
workflow.add_edge("casual", "Memory")

workflow.add_edge("coding", "parent")
workflow.add_conditional_edges(
    "parent",
    lambda state : "error" in state["result"].lower(),{
        True  : "child",
        False : "Memory"
    }
)


workflow.add_edge("child", "coding")

app = workflow.compile()  # Compile the workflow into an app object

if __name__ == "__main__":
    # This code will now ONLY run when you execute "python agent.py"
    # It will NOT run when app_server.py imports it.
    
    task = """What's the name of your creater?"""
    final_result = app.invoke({"task" : task})

    print("\n---FINAL RESULT---")
    print(final_result.get('result', 'Workflow finished.'))