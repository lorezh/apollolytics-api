import re
from dotenv import load_dotenv
from langchain.schema import HumanMessage, SystemMessage  # Custom schema definitions for messages
import llm.ressources.prompts as prompts
import llm.ressources.humour_ressources as humour_ressources

load_dotenv()

import logging
import os
import time
import json
import httpx

from llm.load_llm import load_llm

class Memeifier:
        
    def __init__(self, model_name: str):
        """
        Initializes a new instance of the propaganda detection class.

        Args:
            model_name (str): Identifier for the OpenAI model to be used.
        """
        # Initialize the language model with specific parameters
        self.llm = load_llm(model_name,
                            temperature=0,  
                            model_kwargs={
                                "response_format": {"type": "json_object"}
                            })
        # Imgflip credentials
        self.imgflip_username = "Apollolytics"
        self.imgflip_password = "Apollolytics2025!"
        self.imgflip_url = "https://api.imgflip.com/caption_image"
        
    async def process_statement(self, statement, context, technique, target, frame, template_name, category):
        """
        Creates a meme based on the provided params and the humour ressources.

        Args:
            statement (str): The statement to be processed.
            context (dict): the context of the meme.
            technique (str): The propaganda technique used in the statement.
            target (str): The target of the meme.
            frame (str): The frame of the meme.
            template (str): The template of the meme.
            cagtegory (str): Only the technique category.

        Returns:
            obj: The created meme.
        """
        meme_templates = self.load_meme_database()
        selected_template = self.get_template_from_name(template_name, category, meme_templates)
        meme_template_id = selected_template.get("template_id", None)
        humour_policy = humour_ressources.HUMOUR_POLICY
        humour_style = humour_ressources.HUMOUR_STYLE
        input_text = f"""Statement: {statement}\nContext:\n{context}\nTechnique: {technique}\nTarget:\n{target}\nFrame: {frame}\nTemplate:\n{selected_template}\nHumour Policy: {humour_policy}\nHumour Style: {humour_style}\n"""

        prompt = [
            SystemMessage(
                content=prompts.CREATE_JOKE_PROMPT
            ),
            HumanMessage(
                content=input_text  
            ),
        ]

        try:
            if meme_template_id:
                start_time = time.time()
                output = await self.llm.ainvoke(prompt)
                output = json.loads(output.content)
                params = self.create_joke_params(meme_template_id, output)
                async with httpx.AsyncClient() as client:
                    response = await client.post(self.imgflip_url, data=params)
                    data = response.json()
                    if data["success"]:
                        logging.info(f"create_joke took {time.time() - start_time} seconds")
                        return {
                            "output": data["data"]["url"],
                            "joke": output,
                            "status": "success"
                        }
                    else:
                        raise Exception(f"Error creating meme: {data['error_message']}")
        except Exception as e:
            logging.error(f"An error occurred during creating the joke: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
        
    def create_joke_params(self, template_id, joke_output):
        """
        Creates the parameters for the Imgflip API request.

        Returns:
            dict: The parameters for the Imgflip API request.
        """
        # Dynamically extract all text fields from the joke_output
        params = {
            "template_id": template_id,
            "username": self.imgflip_username,
            "password": self.imgflip_password
        }

        for key, value in joke_output.items():
            if key.startswith("text") and value:
                index = key[4:]  # extract the number after "text"
                box_key = f"boxes[{index}][text]"
                params[box_key] = value
        return params
    
    def parse_context_string(self, input_string):
        '''
        Parses a context string formatted with headers and subkeys.'''

        # Clean up leading '**' and unnecessary newlines
        cleaned = input_string.strip().lstrip('*').strip()

        # Split into three sections by header keywords
        sections = re.split(r'\n(?=[a-z]+:)', cleaned)
        section_dict = {}
        
        # Build a map for the three sections
        for section in sections:
            if section.startswith('context:'):
                section_dict['context'] = section[len('context:'):].strip()
            elif section.startswith('target:'):
                section_dict['target'] = section[len('target:'):].strip()
            elif section.startswith('frame:'):
                section_dict['frame'] = section[len('frame:'):].strip()

        # Helper function to parse subkeys within a section
        def parse_subkeys(section_text, expected_keys):
            output = {key: "" for key in expected_keys}
            # Regex pattern to find "- key: value" pairs, capturing multiline values
            pattern = re.compile(r'-\s*([a-z_]+):\s*(.*?)(?=\n-\s*[a-z_]+:|\Z)', re.DOTALL)
            for match in pattern.finditer(section_text):
                key, value = match.groups()
                if key in output:
                    output[key] = value.strip().replace('\n', ' ')
            return output

        result = {
            "context": parse_subkeys(section_dict.get("context", ""), ["main_context", "attacking_points", "existing_jokes"]),
            "target": parse_subkeys(section_dict.get("target", ""), ["main_target", "additional_information", "attacking_points", "existing_jokes"]),
            "frame": parse_subkeys(section_dict.get("frame", ""), ["main_frame"])
        }

        return result

    async def parse_context(self, location, context, technique):
        """
        Extracts the context JSON content from a string.

        Processes the location and category together with the context JSON with string values for 'target', 'context' and 'frame', and returns the specified dictionary structure.

        Args:
            statement (str): The statement to be processed.
            context (dict): Should contain string values for the keys:
                            'target', 'context' and 'frame'.

        Returns:
            dict: A dictionary with statement and technique as keys and context keys.
        """

        try:
            parsed_json = self.parse_context_string(context)
        except (SyntaxError, ValueError) as e:
            raise ValueError(f"Failed to parse input string. Error: {e}")
        try:
            parsed_context = {
                "statement": location,
                "context": parsed_json.get("context", ""),
                "technique": technique,
                "target": parsed_json.get("target", ""),
                "frame": parsed_json.get("frame", "")
            }
            
            return parsed_context
        
        except Exception as e:
            logging.error(f"An error occurred during parsing: {e}", exc_info=True)
            return f"Error: {str(e)}"

    async def select_template(self, category, frame):
        """
        Selects a template based on the category and frame.

        Args:
            category (str): The category of the meme.
            frame (str): The frame of the meme.

        Returns:
            dic: The selected template.
        """
        main_frame = frame['main_frame']
        meme_templates = self.load_meme_database()
        frame_set = self.get_frames_for_technique(category, meme_templates)

        if frame_set.__len__() == 0:
            logging.error(f"No templates found for category: {category}")
            return None
        
        input_text = f"""Statement frame: {main_frame}\nMeme Templates:\n{frame_set}"""

        prompt = [
            SystemMessage(
                content=prompts.SELECT_TEMPLATE_PROMPT
            ),
            HumanMessage(
                content=input_text  
            ),
        ]

        llm_4o = load_llm(model_name="gpt-4o",
                            temperature=0,  
                            model_kwargs={
                                "response_format": {"type": "json_object"}
                            })
        
        # Get the model's output given the prompt
        try:
            start_time = time.time()
            output = await llm_4o.ainvoke(prompt)
            logging.info(f"select_template took {time.time() - start_time} seconds")
            return {
                "output": json.loads(output.content),
                "status": "success"
            }
        except Exception as e:
            logging.error(f"An error occurred during selecting template: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
        
    def load_meme_database(self):
        """
        Load the meme database from a JSON file.
        
        Returns:
            dict: Parsed JSON data as a Python dictionary.
        """
        file_path = os.path.join(os.path.dirname(__file__), "ressources", "meme_templates.json")
        with open(file_path, 'r') as f:
            meme_db = json.load(f)
        return meme_db

    def get_frames_for_technique(self, technique, meme_db):
        """
        Create a string listing the frames for all templates of a given technique.
        
        Args:
            technique (str): The name of the technique.
            meme_db (dict): The loaded meme database.
        
        Returns:
            str: Formatted string listing 'frame of [template_name]: [template_frame]'.
        """
        templates = meme_db.get(technique, [])
        if not templates:
            return f"No templates found for technique '{technique}'."

        frames = []
        for template in templates:
            template_name = template.get('template_name', 'Unknown Template')
            frame = template.get('frame', 'No frame provided.')
            frames.append(f"Frame of {template_name}: {frame}")


        return '\n'.join(frames)
    
    def get_template_from_name(self, template_name, technique, meme_db):
        """
        Get a template from the meme database by its name.

        Args:
            template_name (str): The name of the template to retrieve.
            technique (str): The name of the technique.
            meme_templates (dict): The meme templates database.

        Returns:
            dict: The selected template.
        """
        templates = meme_db.get(technique, [])
        if not templates:
            return f"No templates found for technique '{technique}'."

        for template in templates:
            if template['template_name'] == template_name:
                return template
        return None