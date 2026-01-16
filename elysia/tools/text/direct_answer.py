import dspy
from elysia.objects import Response, Tool
from elysia.tree.objects import TreeData
from elysia.util.client import ClientManager
from elysia.util.elysia_chain_of_thought import ElysiaChainOfThought
from elysia.tools.text.prompt_templates import TextResponsePrompt, ComplexityScope

class DirectAnswer(Tool):
    def __init__(self, **kwargs):
        super().__init__(
            name="direct_answer",
            description="""
            Directly answer the user's prompt using the internal knowledge of the Large Language Model.
            Use this tool when:
            - The "Search" feature is disabled.
            - The user's request is simple conversation, chitchat, or greetings.
            - The request requires creative writing or logic but no external information.
            - You have decided that retrieval is not necessary for this specific query.
            
            This tool handles the selection of the appropriate model (Base vs Complex) automatically.
            """,
            status="Thinking...",
            inputs={},
            end=True,
        )

    async def is_tool_available(
        self,
        tree_data: TreeData,
        base_lm: dspy.LM,
        complex_lm: dspy.LM,
        client_manager: ClientManager | None = None,
        **kwargs,
    ):
        # This tool is always available as a fallback or direct choice
        return True

    async def __call__(
        self,
        tree_data: TreeData,
        inputs: dict,
        base_lm: dspy.LM,
        complex_lm: dspy.LM,
        client_manager: ClientManager | None = None,
        **kwargs,
    ):
        # 1. Determine Complexity using Base LM (fast & cheap)
        # We classify the prompt to decide whether to upgrade to the complex model
        complexity_classifier = dspy.Predict(ComplexityScope)
        
        try:
            classification = await complexity_classifier.aforward(
                user_prompt=tree_data.user_prompt,
                lm=base_lm
            )
            complexity = classification.complexity
            # Extract clean string if it comes with artifacts
            if hasattr(complexity, 'split'):
                 complexity = complexity.split('\n')[0].strip()
        except Exception:
            # Fallback to Complex if classification fails to be safe
            complexity = "Complex"

        # 2. Select Model based on complexity
        if complexity == "Simple":
            target_lm = base_lm
        else:
            target_lm = complex_lm
            
        # 3. Generate Response
        # We use ElysiaChainOfThought passing environment=False so it doesn't try to inject RAG context
        text_response_generator = ElysiaChainOfThought(
            TextResponsePrompt,
            tree_data=tree_data,
            environment=False,
            tasks_completed=True,
            message_update=False,
        )

        output = await text_response_generator.aforward(
            lm=target_lm,
        )

        yield Response(text=output.response)
