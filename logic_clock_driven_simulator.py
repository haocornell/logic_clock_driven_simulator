from __future__ import annotations
import os
import json

import heapq
from itertools import count

from openai import AsyncOpenAI, AsyncStream
from openai import AzureOpenAI

from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)                                                                                                                       

# pip install azure-ai-inference
from dotenv import load_dotenv
import os
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential

endpoint = 'https://aoctoai25922176693.cognitiveservices.azure.com/' #'https://mihao-m5wrou16-northcentralus.openai.azure.com/'
api_version = '2025-04-01-preview' #'2024-08-01-preview'
model = 'gpt-5.2' #'gpt-4o'

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version
    )

system_prompt = {"role": "system", "content": "You are a helpful assistant."}

def generate_conversation(data):
    
    # construct prompt
    request = {"role": "user", "content": f"""
        {data}
"""}
  
    response = client.chat.completions.create(
        model=model,
        messages= [system_prompt, request],
        temperature = 0.1,
        max_completion_tokens = 4096 #max_tokens=500
    )
    msg = response.choices[0].message

    return msg.content

def generate_action(data, functions):
    # construct prompt
    request = {"role": "user", "content": f"""
        {data}
"""}
    response = client.chat.completions.create(
        model=model,
        messages= [system_prompt, request],
        functions=functions,
        function_call="auto",  # Let the model decide when to call a function
        temperature = 0.1,
        max_completion_tokens = 4096 #max_tokens=500
    )
    msg = response.choices[0].message
    refusal = msg.refusal

    function_call = msg.function_call
    return function_call

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import List, Optional
import random

@dataclass
class IncidentState:
    id: str
    conversation_history: str = ''
    dc_impact_state: str = ''
    dc_impact_known: bool = False
    start_recovery: bool = False

    def add_msg(self, ts: str, who: str, msg: str) -> None:
        update = f"{ts} <{who}> {msg}"
        self.conversation_history += update
        print(update)

    def act(self, who: str, msg: str) -> None:
        pass


class BaseSRE(ABC):
    def __init__(self, name: str, role: str) -> None:
        self.name = name
        self._role = role

    @property
    def who(self) -> str:
        return f"{self.name} ({self._role})"

    @property
    def role(self) -> str:
        return f"{self._role}"
    
    @abstractmethod
    def one_step(self, istate: IncidentState, event: dict[str, Any]) -> None:
        """Perform exactly one step of investigation/mitigation on the incident."""

class StorageSRE(BaseSRE):
    def one_step(self, istate: IncidentState, event: dict[str, Any]) -> None:
        pass

class NetworkSRE(BaseSRE):
    def one_step(self, istate: IncidentState, event: dict[str, Any]) -> None:
        pass

class DirectDriveSRE(BaseSRE):
    def __init__(self, name: str, role: str) -> None:
        super().__init__(name, role)
        self.knowledge: str = """I am a DRI for direct drive service. My knowledge include
                          1. hardware can meltdown when a cluter temperature is over 40 Celsius. 
                          2. in norway west, there are directive drive service clusters DD-1 in colo2, DD2-2 in colo2 and DD-3 in colo1. 
                             There are also clusters DD-7 and DD-8 in norway east

                        actions I can take include 
                              1. SHUTDOWN <cluster> 
                              2. RESTART <cluster> 
                              3. HEALTH_CHECK <cluster> 
                              4. ASK <question> 
                              5. NONE

                        item enclosed wit angular bracket is the argument of the action. For example, action ASK has an argument 
                        which is supposed to be question posted on the bridge to retrieve related information.
                        """
        self.functions = [
    {
        "name": "SHUTDOWN",
        "description": "shutdown a list of clusters for purposes like avoiding meltdown under the high temperature.",
        "parameters": {
            "type": "object",
            "properties": {
                "clusters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Indicate a list of cluster names to shutdown."
                },
            },
            "required": ["clusters"],
        },
    },
    {
        "name": "RESTART",
        "description": "restart a list of clusters to get them into services again specifically after power or thremal outage.",
        "parameters": {
            "type": "object",
            "properties": {
                "clusters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Indicate a list of cluster names to restart."
                },
            },
            "required": ["clusters"],
        },
    },
    {
        "name": "ASK",
        "description": "Ask a question in the bridges to get related information in order to make a decision.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to be posed in the bridge in order to get information about the onging incident."
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "NOOP",
        "description": "doing nothing.",
    }]

        self.clusters = {'DD-1':'UP', 'DD-2':'UP', 'DD-3': 'UP', 'DD-7': 'UP', 'DD-8':'UP'}
    def one_step(self, istate: IncidentState, event: dict[str, Any]) -> None:
        if event['tag'] == 'CLOCK_EVENT':
    
            # check whether we need to update the istate. If there is a change, create a global event
            context = f"""Given the conversation history and my knowledge, indicates what action in terms of function calls should be taken. 

                          bridge conversation history:
                          {istate.conversation_history}

                          my knowledge:
                          {self.knowledge}

                          clusters state: {self.clusters}

                          Be aware of cluster states. If a cluster is down already, there is no need to shut it down again or a cluster is up, then RESTART is not needed. If there are no updates on DC situations, then no need to keep asking questions.
                            
            """
            func = generate_action(context, self.functions)
            #print(func)
            if not func or func.name == 'NONE':
                push_item({"timestamp": ts_minute + 1, "target": self.role, 'tag': 'CLOCK_EVENT'})
                return

            argument = func.arguments
            post = ''
            try:
                args = json.loads(argument) if isinstance(argument, str) else argument
                if func.name == 'SHUTDOWN' or func.name == 'RESTART':
                    post = f"{func.name} {args['clusters']}" 
                    for cluster in args['clusters']:
                        self.clusters[cluster] = 'UP' if func.name == 'RESTART' else 'DOWN'
                elif func.name == 'ASK':
                    post = f"{args['question']}"
            except json.JSONDecodeError as e:
                pass

            if post:
                istate.add_msg(ts_minute, self.role, post)

            if func.name == 'ASK':
                push_item({"timestamp": ts_minute + 1, "target": self.role, 'tag': 'CLOCK_EVENT'})
            else:
                push_item({"timestamp": ts_minute + 15, "target": self.role, 'tag': 'ACTION_DONE', 'ACTION': func})
        elif event['tag'] == 'ACTION_DONE':
            push_item({"timestamp": ts_minute + 1, "target": self.role, 'tag': 'CLOCK_EVENT'})

class DCIM(BaseSRE):
    def one_step(self, istate: IncidentState, event: dict[str, Any]) -> None:
        if event['tag'] == 'CLOCK_EVENT':
            push_item({"timestamp": ts_minute + 1, "target": "DCIM", 'tag': 'CLOCK_EVENT'})
    
            # check whether we need to update the istate. If there is a change, create a global event
            # and update everyperson
            update = ''
            if ts_minute == 10:
                update = "Norway west has a thermal event. The chiller pumps failed and they are being fixed by landlord\n"
                
            elif ts_minute == 30:
                update = "It is confirmed that only colo2 is impacted. It is not clear when pumpt starts to take effect. Temperature remains high, around 60 celcius in colo2. colo1 has normal temperature now."
    
                istate.dc_impact_known = True
            elif ts_minute == 60:
                update = "Currently, the temperature in colo2 has remained at 60 celcius. No more data is available"
                
            elif ts_minute == 120:
                update = "Currently, the temperature in colo2 has dropped to normal."
                istate.start_recovery = True

            if update:    
                context = f"""Generate a sentence to simulate a status report from a DC incident manager to the bridge about latest update shown below:

                    {update}"""  

                post = generate_conversation(context)

                istate.dc_impact_state += f"{update}\n"
                istate.add_msg(ts_minute, self.role, post)
    
                push_item({"timestamp":  ts_minute + 1, "target": "ALL", 'tag': 'HISTORY_UPDATE', 'update': post})

        elif event['tag'] == 'TARGET_QUESTION':
            question = event['question']
            # generate answer based on current istate
            context = f"""
                         Based on the DC istate below, answer the question from AIM. If there are no related informaion,
                         just answer it is not known. Currently, DC istate is below:
                           {istate.dc_impact_state}
    
                         answer the question:{question}.
                    """
            answer = generate_conversation(context)
            push_item({"timestamp":  ts_minute + 1, "target": event['from'], 'tag': 'TARGET_ANSWER','answer': f'{answer}'})
    
            istate.add_msg(ts_minute, self.role, answer)
        elif event['tag'] == 'HISTORY_UPDATE':
            pass
           

class AIM(BaseSRE):
    def __init__(self, name: str, role: str) -> None:
        super().__init__(name, role)
        self.last_status_query_ts: int =  -1  # instance variable

    def one_step(self, istate: IncidentState, event: dict[str, Any]) -> None:
        if event['tag'] == 'CLOCK_EVENT':
            push_item({"timestamp": ts_minute + 1, "target": "AIM", 'tag': 'CLOCK_EVENT'})
            # check whether we need to update the state. If there is a change, create a global event
            # and update everyperson
            if not istate.dc_impact_known and (self.last_status_query_ts == -1 or  (ts_minute - self.last_status_query_ts) > 10): # ask a tageted question againt DCIM
                context = f"""Generate a sentence to simulate a quetion from a incident manager to DC incident manager asking about the current status of thermal event and specific impact details. using [DC Incident Manager] to indicate this is to him/her."""  
                q = generate_conversation(context)
                self.last_status_query_ts = ts_minute
                push_item({"timestamp": ts_minute + 1, "target": "DCIM", 'tag': 'TARGET_QUESTION', 'from': 'AIM', 'question': q})    
                istate.add_msg(ts_minute, self.role, q)
        elif event['tag'] == 'TARGET_ANSWER':
            # test stuff
            pass
        elif event['tag'] == 'HISTORY_UPDATE':
            if istate.start_recovery:
                # ground truth
                print("SHOULD START THE RECOVERY PROCESS.")
            pass

# maintain a logical clock to drive the progress.
counter = count()  # unique increasing tie-breaker
h = []

def push_item(d):
    heapq.heappush(h, (d["timestamp"], next(counter), d))

def pop_item():
    return heapq.heappop(h)[2]  # returns the dict

ts_minute = 0

#bootstrap
push_item({"timestamp": ts_minute, "target": "ALL", 'tag': 'CLOCK_EVENT'})

aim = AIM("ming", "AIM")
dcim =  DCIM("ryan", "DCIM")
ddim = DirectDriveSRE('zhenfeng', 'DDIM')

istate = IncidentState(
        id="INC-1042",
    )
responders: List[BaseSRE] = [ aim, dcim ]

roles = {'DCIM':dcim, 'AIM':aim, 'DDIM': ddim}

while(ts_minute < 600):
    # do things
    event = pop_item()
    
    # update global clock
    ts_minute = event['timestamp']
    target = event['target']

    if target == 'ALL':
        for k, v in roles.items():
            v.one_step(istate, event)
    else:
        roles[event['target']].one_step(istate, event)
