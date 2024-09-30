class BookReviewStack(Stack):
    def __init__(self, scope: Construct, identifier: str, **kwargs) -> None:
        super().__init__(scope, identifier, **kwargs)

        # Operation #1: create a brief overview
        brief_overview = execute_anthropic_claude_interaction(
            self,
            "Create Brief Overview",
            prompt=sfn.JsonPath.format(
                "Craft a concise overview of the book {} in 1-2 sentences.",
                sfn.JsonPath.string_at("$$.Execution.Input.novel"),
            ),
            include_conversation_history=False,
        )

        # Operation #2: provide plot details
        plot_details = execute_anthropic_claude_interaction(
            self,
            "Provide Plot Details",
            prompt=sfn.JsonPath.format(
                "Detail the plot of the book {} in a structured paragraph.",
                sfn.JsonPath.string_at("$$.Execution.Input.novel"),
            ),
        )

        # Operation #3: explore themes
        theme_exploration = execute_anthropic_claude_interaction(
            self,
            "Explore Themes",
            prompt=sfn.JsonPath.format(
                "Explore and discuss the central themes of the book {}.",
                sfn.JsonPath.string_at("$$.Execution.Input.novel"),
            ),
        )

        # Operation #4: critique the style
        style_critique = execute_anthropic_claude_interaction(
            self,
            "Critique the Style",
            prompt=sfn.JsonPath.format(
                "Critique the narrative style and overall tone of the book {}.",
                sfn.JsonPath.string_at("$$.Execution.Input.novel"),
            ),
        )

        # Operation #5: synthesize the review
        review_synthesis = execute_anthropic_claude_interaction(
            self,
            "Synthesize the Review",
            prompt=sfn.JsonPath.format(
                (
                    'Integrate the analysis from previous steps to synthesize a complete review titled "{} - A Comprehensive Literature Analysis" for our review platform. '
                    "Include an introduction and a conclusion to ensure a five-paragraph article."
                ),
                sfn.JsonPath.string_at("$$.Execution.Input.novel"),
            ),
            max_tokens_to_sample=1000,
            maintain_conversation_flow=False,
        )

        finalize_response = sfn.Pass(
            self,
            "Finalize Response",
            output_path="$.model_outputs.response",
        ) #A

        # Sequence the operations into a coherent workflow
        operation_chain = (
            brief_overview.next(plot_details) #B
            .next(theme_exploration)
            .next(style_critique)
            .next(review_synthesis)
            .next(finalize_response)
        )
        sfn.StateMachine(
            self,
            "BookReviewMachine",
            state_machine_name="ComprehensiveReview-Book",
            definition_body=sfn.DefinitionBody.from_chainable(operation_chain),
            timeout=Duration.seconds(300),
        )
