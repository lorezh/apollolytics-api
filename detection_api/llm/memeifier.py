from dotenv import load_dotenv

from detection_api.llm.contextualizer import Contextualizer

load_dotenv()

import logging
import os
import time
import pandas as pd
from langchain import hub
from langchain.agents import Tool
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.tools import BaseTool
from llm.load_llm import load_llm

from llm.google_retriever import InformationRetrieval

class Memeifier:
    def __init__(self, model_name: str):
        self.llm = load_llm(model_name,
                            temperature=0,
                            streaming=True)




    