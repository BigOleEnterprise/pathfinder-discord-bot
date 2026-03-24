Unsent prompts:

- Geting this error: 
ERROR - Error in /ask command: expected view parameter to be of type View not NoneType
Traceback (most recent call last):

think this is coming from this line where no search results return none:
view = SourcesView(search_results) if search_results else None

how do I make this fail safely, so it still returns type View

