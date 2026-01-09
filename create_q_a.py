#!/usr/bin/env python3
"""
stream_chunk_process.py

Read a text file and process it in a streaming way, chunked by N lines
(default 2000). Nothing is persisted; each chunk is handled then discarded.

Usage:
  python stream_chunk_process.py input.txt
  python stream_chunk_process.py input.txt --chunk-lines 2000
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

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

system_prompt = {"role": "system", "content": """You are a helpful assistant. You are given a piece of knowledge extracted from oncall experiences. You are supposed to construct a question which can be answered by leveraging this piece knowledge. In addition, answer this question as well. Please output question and answer together with one on each line.  
                 """}

def gen_q_a(knowledge: str) -> str:
    
    # construct prompt
    request = {"role": "user", "content": f"""
        The knowledge for question and answere generation is below:
        {knowledge}
"""}
  
    response = client.chat.completions.create(
        model=model,
        messages= [system_prompt, request],
        temperature = 0.1,
        max_completion_tokens = 4096 #max_tokens=500
    )
    msg = response.choices[0].message

    print(msg.content)
    return msg.content

def gen_data(knowledge_file: str) -> dict[str, Any]:
    """
    Replace with your real per-chunk logic.
    This example just prints the chunk number and the first/last line numbers.
    """
    data = []
    with knowledge_file.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith('-'):
                r = gen_q_a(line)
                q, a = r.split('\n')
   
                q = q.strip()
                prefix = 'question:'
                if q[:len(prefix)].casefold() == prefix:
                    q = q[len(prefix):].lstrip()

                a = a.strip()
                prefix = 'answer:'
                if a[:len(prefix)].casefold() == prefix:
                    a = a[len(prefix):].lstrip()
    
                data.append({'knowledge': line, 'question': q, 'answer': a})
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream-process a file in fixed line chunks.")
    parser.add_argument("input_file", type=str, help="Path to input text file")
    parser.add_argument("output_file", type=str, help="Path to output text file")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output_file)
    data = gen_data(input_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

