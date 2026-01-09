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

system_prompt = {"role": "system", "content": """You are a helpful assistant. You ar egiven a voice transcript history on a oncall bridge. Please help to extract insight, knowledge facts which can help people to deal with similar incidents. Each piece of knowledge should capture key point but be concise.  
                 """}

def extract_knowledge(previous_knowledge, chunk):
    
    # construct prompt
    request = {"role": "user", "content": f"""
        Below is a list of knowledges extracted from previous conversation history. 
        {previous_knowledge}

        This is current chunk of conversation history:
        {chunk}

        Please extract insight, knowledge facts which can help people to deal with similar incidents. Should avoid generating duplicated knowledges with existing ones. 
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



def iter_line_chunks(file_path: Path, chunk_lines: int) -> Iterable[List[str]]:
    """Yield up to chunk_lines lines at a time (streaming)."""
    if chunk_lines <= 0:
        raise ValueError("chunk_lines must be a positive integer")

    buf: List[str] = []
    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            buf.append(line)
            if len(buf) == chunk_lines:
                yield buf
                buf = []
        if buf:
            yield buf


def process_chunk(knowledges: str, chunk_index: int, lines: List[str]) -> str:
    """
    Replace with your real per-chunk logic.
    This example just prints the chunk number and the first/last line numbers.
    """
    # Example "work": count non-empty lines
    new_knowledge = extract_knowledge(knowledges, "\n".join(lines))
    return knowledges + '\n' + new_knowledge


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream-process a file in fixed line chunks.")
    parser.add_argument("input_file", type=str, help="Path to input text file")
    parser.add_argument("--chunk-lines", type=int, default=2000, help="Lines per chunk (default: 2000)")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    knowledges = ''
    for idx, chunk in enumerate(iter_line_chunks(input_path, args.chunk_lines), start=1):
        process_chunk(knowledges, idx, chunk)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

