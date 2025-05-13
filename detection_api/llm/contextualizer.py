from dotenv import load_dotenv

load_dotenv()

import logging
import os
import time
import pandas as pd
from langchain import hub
from langchain.agents import Tool
from langchain.agents import create_react_agent, AgentExecutor
from detection_api.llm.ressources.parsers import MemeParser
from langchain_core.tools import BaseTool
from llm.load_llm import load_llm

from llm.google_retriever import InformationRetrieval

# Load environment variables, including API keys for Google and OpenAI.

GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "default_cse_id")
GOOGLE_APIKEY = os.getenv("GOOGLE_API_KEY", "default_api_key")

# Load excluded URLs from a CSV file
file_path = os.path.join(os.path.dirname(__file__), "ressources", "mediabiasfactcheck_fakenews.csv")
fake = pd.read_csv(file_path)
fake = fake[fake["Traffic/Popularity"] != "Minimal Traffic"]
excluded_sites = fake["source_link"].apply(lambda x: x.split("//")[-1].split("www.")[-1].split("/")[0])


def render_text_description(tools: list[BaseTool]) -> str:
    """Render the tool name and description in plain text.

    Args:
        tools: The tools to render.

    Returns:
        The rendered text.

    Output will be in the format of:

    .. code-block:: markdown

        search: This tool is used for search
        calculator: This tool is used for math
    """
    descriptions = []
    for tool in tools:
        description = f"<tool>\n{tool.name}:\n{tool.description}\n</tool>"
        descriptions.append(description)
    return "\n".join(descriptions)


google_description = """Get previews of the top google search results to get more information about the statement. The function always returns the next 10 results and can be called multiple times. If initial results seem unrelated you may use quotation marks to search for an exact phrase. Use a minus sign to exclude a word from the search.  Use before:date and after:date to search for results within a specific time period. Do not google the entire statement verbatim."""


def get_prompt(date, originator):
    prompt = hub.pull("hwchase17/react")

    prompt_template = """You are an expert contextualizer tasked to expanding and enriching understanding around potentially misleading statements to make sure users are safe and well informed.
Your role is to provide balanced, accurate, concise, and helpful context about a given statement.

You have access to the following tools for your research:
<tools>
{tools}
</tools>

You may use each tool up to three times.

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat 3 times)
Thought: I now have sufficient information to provide context for the user.
Final Answer: The context demanded by the user.

**Final Response Format:**
- **Context:** (Provide a precise, concise, and factual summary of the topic, incorporating context from the sources)
- **Warning:** (Explain potential risks of misinformation precisely, including how the statement might be misleading and what important context it might be missing)
- **Sources:** (List all important sources by their reference numbers, e.g., [1], [2], [3])

**Example Final Answer in case no results are found:**
Context: No relevant information found.
Warning: The statement may not be widely discussed or may not have been indexed by search engines.
Sources: None

**Example Final Answer:**  
Context: Electric vehicles (EVs) produce fewer greenhouse gas emissions over their lifetime compared to gasoline-powered cars, according to studies [1], [2]. EVs emit no tailpipe emissions and are more efficient in energy use. However, their production, particularly the manufacturing of batteries, involves significant environmental impact due to energy-intensive processes and raw material extraction [3].
Warning: Statements claiming that EVs are "worse for the environment" may focus exclusively on production emissions, ignoring the substantial operational emissions savings during usage. Conversely, claims that EVs are "entirely green" may overlook the environmental impacts of mining lithium, cobalt, and other materials used in battery production.
Sources: 
- [1] EPA Report on Electric Vehicle Myths (2023-Aug)
- [2] MIT Climate Portal Analysis (2024-Jan)
- [3] Environmental Impact Study (2023-Dec)
    
Begin your analysis now!

Question:
Contextualise the statement: '{statement}'{originator_section}{date_section}
Thought:{agent_scratchpad}"""
    date_section = ""
    originator_section = ""
    if date:
        date_section = " on {date}"
    if originator:
        originator_section = " made by {originator}"
    prompt_template = prompt_template.replace("{date_section}", date_section)
    prompt_template = prompt_template.replace("{originator_section}", originator_section)

    prompt.template = prompt_template
    return prompt

def get_prompt_memeify(date, originator, technique):
    prompt = hub.pull("hwchase17/react")

    prompt_template = """You are an expert contextualizer and meme strategist tasked with expanding and enriching understanding around potentially misleading statements. Your mission is to ensure users are well-informed, factually grounded, and equipped with reliable material that may later support the creation of accurate, coherent, and impactful jokes or memes.

## Your Role is Twofold:
1. **Provide balanced, accurate, concise, and helpful context** about the given statement.
2. **Analyze the statement for attacking points and humor-enabling information** 

Apply your roles by following these steps precisely:

### Disclaimer:
** Do Not Generate a Joke Yourself:**  
You are not tasked with creating or suggesting any joke, meme, or humorous content.  
Your role is strictly to collect **reliable factual groundwork, criticisms, controversies, contradictions, and examples of existing ridicule**. This material is intended to inspire the **manual creation of a joke or meme later by a human writer.**

### Step 1: Contextualise the statement
Take on the first role described above and provide a precise, concise, and factual summary of the topic, incorporating context from the sources.
- Investigate the statement **strictly in its original form**.  
- Do not generalize, paraphrase, or broaden the research to similar claims.  
- This output should be referenced as the **Context**.

### Step 2: Search for Attacking Points and Humor Potential  
- Based on the context you discovered, take on the second role described above and **search for additional attacking points** (such as contradictions, fun angles, controversies, falsehoods, scandals, hypocrisy, logical inconsistencies, or criticisms) that could be used for humor or meme creation and are:
  - **Directly tied to the statement itself**,  
  - Or **clearly related to the factual context you discovered around the statement**.  
- Additionally, research whether **existing jokes, memes, satire, or public ridicule** have already been made: 
  - About this exact statement itself (not similar claims, not related topics, but the exact claim in the exact same context as given),
  - Or about the factual context you discovered regarding the statement.
  The focus should be on examples where this particular statement, exactly as given, has already been mocked, satirized, or turned into humor by others.
  Only include material if it clearly and directly references the statement or the discovered context. Ignore anything that is only broadly related.

**Important Selection Criteria:**  
- Only include attacking points, weak spots, contradictions, or examples of ridicule if they **directly refer to the statement itself or to the discovered context**.  
- Disregard any material that relates only broadly to the topic but does not clearly connect to the specific statement or its contextual background.
- If there are existing jokes, memes, satire, or public ridicule related to the statement or its context, describe in natural language the joke, meme, satire and why it's funny.

### Step 3: Search for a Target 
If the statement identifies a **target** (e.g., person, group, company, organization), you must:
- Detect and define the **target**.
- Research background information on the **target**.
- Search for **fun angles, weaknesses, or contradictions** about the target that could be used for humor or meme creation.
- Search for **attacking points, jokes, satire, public criticism, or memes** already circulating about the target.

**Important Selection Criteria:**  
- Only include attacking points, weak spots, contradictions, or examples of ridicule if they **directly refer to the target**.  
- Disregard any material that relates only broadly to the target.
- If there is no target, the target is not relevant or the target is not a person, group, company, or organization, you must state that there is no target.
- If there are existing attacking points, jokes, satire, public criticism, or memes related to the target, describe in natural language the joke, meme, satire and why it's funny.

### Step 4: Frame the Situation
Your task is to create a structured and coherent frame that describes the overall situation surrounding the given statement. This frame serves as an objective, factual description of the environment in which the statement exists. The purpose of this frame is not to generate humor, but to provide a clear characterization of the situation that will later be used to match this environment against descriptions of meme templates and identify which meme style may fit best.
The frame should accurately reflect the dynamics of the situation based on the following input data that you have gathered from the previous steps:

- The main statement itself.
- The propaganda technique in this case: {technique}.
- The factual context explaining the background of the statement.
- The attacking points and controversies found in the context.
- Existing jokes, memes, or ridicule related to the context.
- The target of the statement (if applicable).
- Additional information about the target.
- Attacking points and controversies related to the target.
- Existing jokes, memes, or ridicule related to the target.

**What the Frame Should Capture:**
- The overall theme of the situation: What is the statement about? What key issues are involved?
- The conflict structure: Are there attacks on specific groups, persons, or ideas? Is the statement defensive, aggressive, exaggerated, misleading?
- The emotional tone: Is the situation emotionally charged, accusatory, defensive, fear-based, blame-focused, or moralizing?
- The level of contradiction or controversy: How strongly is the statement or its context disputed? Are there significant opposing facts, scandals, or criticisms?
- The vulnerability of the target (if present): Is the target in a strong or weak position? Are there exposed weak spots, scandals, or known criticisms?
- The level of public ridicule already present: Have jokes, memes, or satire already addressed this statement, its context, or its target?

**Style and Output Requirements for the frame:**
- The frame must be neutral, objective, and descriptive.
- Use clear, structured, and concise language.
- Do not include humor, jokes, exaggeration, or irony.
- Focus on providing an accurate environmental description that allows this situation to be meaningfully compared to descriptions of meme templates.

### Tools at Your Disposal:
<tools>
{tools}
</tools>

You may use each tool up to three times.

### Use the following format:

Question: the input question you must answer  
Thought: you should always think about what to do  
Action: the action to take, should be one of [{tool_names}]  
Action Input: the input to the action  
Observation: the result of the action  
... (this Thought/Action/Action Input/Observation can repeat up to 3 times)  
Thought: I now have sufficient information to provide context and aditional informations for the user to follow precisly and strictly each specified step according to the descriptions.  
Final Answer: The full response demanded by the user respecting the response format.

## **Final Response Answer Format:**
  context: 
    - main_context: Result from Step 1 (Provide a precise, concise, and factual summary of the topic, incorporating reliable context from the sources)
    - attacking_points: First part of the Result from Step 2 (Contradictions, fun angles, controversies, falsehoods, scandals, hypocrisy, logical inconsistencies, or criticisms directly tied to the statement or the context)
    - existing_jokes: Second part of the Result from Step 2 (Already published jokes, memes, or satire clearly referring to the exact statement or context)
  
  target: 
    - main_target: Who or what is the target of the statement, if any
    - additional_information: Key facts, reputation, history of the target
    - attacking_points: Criticism, weak points, public jokes, meme material already known
    - existing_jokes: Already published jokes, memes, or satire clearly referring to the target
  
  frame: 
    - main_frame: Result from Step 4 (A structured and coherent description of the situation)

**Example Responses Answer if no Results are Found:** 
  context: 
    - main_context: No relevant information found.
    - attacking_points: No relevant attacking points identified.
    - existing_jokes: No existing jokes, memes, or ridicule found.
  
  target: 
    - main_target: No target identified.
    - additional_information: No information available.
    - attacking_points: No attacking points found.
    - existing_jokes: No existing jokes, memes, or ridicule found.
  
  frame: 
    - main_frame: No material available to create a frame.

**Example Response Answer:**  
context: 
    - main_context: On April 26, 2025, former U.S. President Donald Trump posted on his social media platform, Truth Social, expressing doubt about Russian President Vladimir Putin's willingness to end the war in Ukraine. In his post, Trump criticized recent Russian missile strikes on civilian areas, suggesting that Putin might not genuinely seek peace but could be manipulating the situation. Trump proposed that alternative strategies, such as 'banking' or 'secondary sanctions,' might be necessary to deal with Putin. This statement came just hours after Trump's meeting with Ukrainian President Volodymyr Zelenskyy at Pope Francis' funeral in the Vatican.
    - attacking_points: Trump’s statement represents a significant shift from his previous approach, where he often avoided directly criticizing Putin and was accused of being overly accommodating toward Russia. The sudden change in tone, especially following his meeting with Zelenskyy, raises questions about the consistency and sincerity of his foreign policy positions. Additionally, Trump's suggestion of secondary sanctions contradicts his earlier skepticism toward punitive measures against Russia, highlighting potential inconsistencies in his stance.
    - existing_jokes: While there are no specific jokes or memes directly referencing this particular statement, there is a long-standing body of satire portraying Trump as being excessively friendly or submissive toward Putin. Popular examples include cartoons showing Trump as a puppet controlled by Putin or portraying their relationship as an unbalanced friendship. These representations mock Trump's perceived deference to Putin and are relevant to the broader context of this statement.
  
  target: 
    - main_target: Vladimir Putin
    - additional_information: Vladimir Putin has served as the President of the Russian Federation for over two decades. Under his leadership, Russia launched a full-scale invasion of Ukraine in 2022, resulting in widespread international condemnation and severe economic sanctions. Putin has been held responsible for numerous human rights violations and attacks on civilian infrastructure during the conflict.
    - attacking_points: Putin's credibility has been seriously undermined by repeated violations of ceasefire agreements and continued military aggression, particularly the targeting of civilian areas. Human rights organizations and international bodies have accused him of committing war crimes, further damaging his global reputation.
    - existing_jokes: Putin is frequently the subject of satire and ridicule, often portrayed as a manipulative autocrat who disregards international law. Common meme themes include depictions of Putin as a dictator, as well as jokes highlighting the contrast between his strongman image and the reality of international isolation and criticism.
  
  frame: 
    main_frame: The situation revolves around a public statement by former U.S. President Donald Trump, where he casts doubt on Russian President Vladimir Putin's intentions to end the war in Ukraine. Trump suggests that Putin may be deceiving him and proposes the use of financial restrictions or secondary sanctions as a response. This statement signifies a major departure from Trump's previous approach, where he often avoided directly criticizing Putin. The statement was made shortly after Trump's meeting with Ukrainian President Volodymyr Zelenskyy, during a time of heightened diplomatic efforts to resolve the conflict. The propaganda technique identified in this case is 'Attack on Reputation'. In this statement, Trump actively questions Putin’s credibility by implying that Putin is not sincere about peace negotiations and is instead manipulating the situation. This technique undermines Putin's trustworthiness and portrays him as deceitful and unreliable. The emotional tone of the situation is accusatory and skeptical, dominated by frustration over continued military aggression and perceived manipulation. The conflict structure involves a direct reputational attack on Putin without specifying personal hostility, focusing instead on his political behavior and intentions. The level of controversy is high, fueled by Trump's historically soft stance toward Putin, which contrasts with his current proposal of harsher measures such as secondary sanctions. This contradiction invites scrutiny of Trump's foreign policy consistency. The vulnerability of the target, Putin, is significant due to well-documented allegations of war crimes, violations of international law, and aggressive military actions against civilian targets. This increases the effectiveness of the 'Attack on Reputation' technique in this context. Public ridicule related to both Trump and Putin is already present. Jokes and memes frequently highlight their relationship, often portraying Trump as submissive or overly friendly toward Putin, and Putin as a manipulative autocrat. These existing cultural references reinforce the environment of reputational challenge and mistrust.

Begin your analysis now!

Question:  
Process the statement acording to the specified steps: '{statement}'{originator_section}{date_section}  
Thought:{agent_scratchpad}"""
    date_section = ""
    originator_section = ""
    if date:
        date_section = " on {date}"
    if originator:
        originator_section = " made by {originator}"
    prompt_template = prompt_template.replace("{date_section}", date_section)
    prompt_template = prompt_template.replace("{originator_section}", originator_section)
    prompt_template = prompt_template.replace("{technique}", technique)

    prompt.template = prompt_template
    return prompt

class Contextualizer:
    def __init__(self, model_name, cse_id=GOOGLE_CSE_ID, api_key=GOOGLE_APIKEY):
        self.llm = load_llm(model_name,
                            max_tokens=4096,
                            temperature=0,
                            streaming=True)

    async def seems_factual(self, statement):
        """
        Determines whether a given statement seems to be a factual statement or an opinion, with a focus on identifying
        statements that could be related to propaganda or disinformation. This function classifies the statement based
        on how fact-like it appears, not on its actual truthfulness. It is particularly useful in contexts where the
        distinction between misleading factual statements and clear opinions is critical.

        :param statement: The statement to classify as seeming fact or opinion, with a consideration for propaganda and disinformation.
        :return: True if the statement seems to be a factual statement (or is designed to appear as such), False if it seems to be an opinion.
        """
        try:
            from langchain.chains import create_tagging_chain
            # Adjust the grading schema to include examples related to propaganda and disinformation.
            grading_schema = {
                "properties": {
                    "fact_label": {
                        "type": "string",
                        "enum": ['0', '1'],
                        # '0' for opinions or statements not attempting to appear factual, '1' for statements that appear factual.
                        "description": "Classify the given statement with an emphasis on identifying potential propaganda or disinformation. \n"
                                       "0: Opinions (e.g., 'Country X's leaders are the best in the world.', 'Only fools believe in climate change.')\n"
                                       "1: Statement Appears Factual or Misleadingly Factual (e.g., 'Country Y has the highest crime rate due to its immigration policies.', 'Recent studies show that vaccines are more harmful than previously thought.', '9/11 was an inside job.')\n"
                                       "Choose '0' or '1' based on whether the statement seems to be presenting a fact or an opinion, with an eye for potentially misleading information."
                    },
                },
                "required": ["fact_label"],
            }

            # Classify the statement with a focus on its appearance as factual or opinionated, considering propaganda and disinformation.
            output_grading = create_tagging_chain(grading_schema, self.llm).run(statement)

            # Interpret the classification result as a boolean value: True for '1' (Seems Factual or Misleadingly Factual) and False for '0' (Opinion or Clearly Biased).
            return output_grading["fact_label"] == '1'
        except Exception as e:
            logging.error(f"Failed to classify statement: {statement} - {str(e)}")
            return False

    def identify_seemingly_factual(self, text):
        """
        Identifies factual information in a given text, with a focus on identifying statements that could be related to propaganda or disinformation.
        This function classifies the statement based on how fact-like it appears, not on its actual truthfulness. The LLM then returns quotes from the text that seem factual.

        :param text: The text to analyze for factual information.
        :return: A list of quotes from the text that seem to be factual statements (or are designed to appear as such).
        """
        from langchain.schema import HumanMessage, SystemMessage
        prompt = [
            SystemMessage(content="""Please read the following text carefully. Identify and return any segments that present information which appears factual, or is designed to appear as such, especially in the context of potential propaganda or disinformation. Please provide the full quotes from the text, remember to return enough content in quote so in a next step the statement can be contextualized, so quotes can span over multiple sentences if needed to be contextualized usefully. A quote should span over a whole sentence at least. If no such segments are found, return 'No factual segments found.' The ouput should be a list of quotes, with each quote on a new line, e.g.:
            Quote1
            Quote2
            Quote3 and so on"""),
            HumanMessage(content=text),
        ]

        output = self.llm(prompt)
        results_lst = output.content.split("\n")
        return results_lst

    async def process_statement(self, statement, date=None, originator=None, memeify=False, technique=None):
        """
        Processes a given statement to perform contextualization, utilizing both Google Custom Search and a language model.

        This method involves several steps:
        1. Parsing the input statement and preparing it for processing.
        2. Initializing a custom search tool with Google search capabilities.
        3. Defining a prompt template for the language model.
        4. Initializing a memory buffer to store conversation history.
        5. Configuring and running an agent that uses the search tool and language model to analyze the statement.
        6. Collecting and formatting the results for return or further processing.

        :param statement: The statement to be processed and contextualized.
        :param date: The date associated with the statement, if available.
        :return: A dictionary containing processed information, including search results and analysis from the language model.
        """

        google_search_tool = InformationRetrieval(cse_id=GOOGLE_CSE_ID,
                                                  api_key=GOOGLE_APIKEY,
                                                  excluded_sites=excluded_sites,
                                                  num_results=10)

        google_private = Tool(
            name='Google',
            func=google_search_tool.search,
            description=google_description,
        )

        prompt = get_prompt_memeify(date, originator, technique) if memeify else get_prompt(date, originator)
        output_parser = MemeParser() if memeify else None

        try:
            tools = [google_private]
            agent = create_react_agent(self.llm,
                                       tools,
                                       prompt,
                                       tools_renderer=render_text_description,
                                       output_parser=output_parser,)
            agent_executor = AgentExecutor(agent=agent,
                                           tools=tools,
                                           verbose=False,
                                           return_intermediate_steps=True,
                                           max_iterations=5)
            agent_executor_input = {"statement": statement}
            if date:
                agent_executor_input["date"] = date
            start_time = time.time()
            result = await agent_executor.ainvoke(agent_executor_input)
            final_answer = result["output"]

            # Return final answer for memeification process
            if(memeify):
                logging.info(f"meme contextualizer took {time.time() - start_time} seconds")
                return {
                    "output": final_answer,
                    "status": "success"
                }     
                   
            # Get the link mapping from the search tool
            link_mapping = google_search_tool.get_link_mapping()

            # Split the answer into sections
            sections = final_answer.split("Sources:")
            if len(sections) == 2:
                main_content, sources_section = sections
                if len(sources_section) > 10:
                    # Find all referenced numbers in the entire text
                    import re
                    all_refs = set(int(num) for num in re.findall(r'\[(\d+)\]', final_answer))

                    # Create new mapping with sequential numbers
                    new_mapping = {}
                    old_to_new = {}
                    new_index = 1

                    # First pass: create mapping for used references only
                    for old_num in sorted(all_refs):
                        if old_num in link_mapping:
                            old_to_new[old_num] = new_index
                            new_mapping[new_index] = link_mapping[old_num]
                            new_index += 1

                    # Replace numbers in main content
                    for old_num, new_num in old_to_new.items():
                        main_content = main_content.replace(f'[{old_num}]', f'[{new_num}]')
                        sources_section = sources_section.replace(f'[{old_num}]',
                                                                  f'[{new_num}]({new_mapping[new_num]})')

                    # Reconstruct the final answer
                    final_answer = main_content + "Sources:" + sources_section

                    # Update link_mapping to only include used references with new numbers
                    link_mapping = new_mapping
                else:
                    final_answer = "No relevant information found."

            logging.info(f"contextualizer took {time.time() - start_time} seconds")

            return {
                "output": final_answer,
                "all_google_results": google_search_tool.all_results,
                "all_queries": google_search_tool.all_queries,
                "retrieved_links": google_search_tool.retrieved_links,
                "retrieved_texts": google_search_tool.retrieved_texts,
                # "link_mapping": link_mapping,  # Add the link mapping to the output
                "status": "success"
            }

        except Exception as e:
            logging.error(f"Failed Parsing: {statement} - {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
