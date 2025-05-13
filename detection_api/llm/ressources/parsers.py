from langchain.schema.agent import AgentAction, AgentFinish
from langchain.agents.agent import AgentOutputParser
import re


class MemeParser(AgentOutputParser):
    def parse(self, text: str):
        text = text.strip()

        # CASE 1: Final Answer
        if "Final Answer:" in text:
            final_output = text.split("Final Answer:")[-1].strip()
            return AgentFinish(
                return_values={"output": final_output},
                log=text
            )

        # CASE 2: Tool Action
        match = re.search(r"Action:\s*(.*?)\s*Action Input:\s*(.*)", text, re.DOTALL)
        if match:
            tool = match.group(1).strip()
            tool_input = match.group(2).strip().strip('"')
            return AgentAction(
                tool=tool,
                tool_input=tool_input,
                log=text
            )

        # CASE 3: Fallback — treat entire output as final
        return AgentFinish(
            return_values={"output": text},
            log=text
        )