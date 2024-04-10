import json
from application.retriever.base import BaseRetriever
from application.core.settings import settings
from application.llm.llm_creator import LLMCreator
from application.utils import count_tokens
from langchain_community.tools import BraveSearch



class BraveRetSearch(BaseRetriever):

    def __init__(self, question, source, chat_history, prompt, chunks=2, gpt_model='docsgpt'):
        self.question = question
        self.source = source
        self.chat_history = chat_history
        self.prompt = prompt
        self.chunks = chunks
        self.gpt_model = gpt_model
    
    def _get_data(self):
        if self.chunks == 0:
            docs = []
        else:
            search = BraveSearch.from_api_key(api_key=settings.BRAVE_SEARCH_API_KEY, 
                search_kwargs={"count": int(self.chunks)})
            results = search.run(self.question)
            results = json.loads(results)
        
            docs = []
            for i in results:
                try:
                    title = i['title']
                    link = i['link']
                    snippet = i['snippet']
                    docs.append({"text": snippet, "title": title, "link": link})
                except IndexError:
                    pass
        if settings.LLM_NAME == "llama.cpp":
            docs = [docs[0]]
        
        return docs
    
    def gen(self):
        docs = self._get_data()
        
        # join all page_content together with a newline
        docs_together = "\n".join([doc["text"] for doc in docs])
        p_chat_combine = self.prompt.replace("{summaries}", docs_together)
        messages_combine = [{"role": "system", "content": p_chat_combine}]
        for doc in docs:
            yield {"source": doc}

        if len(self.chat_history) > 1:
            tokens_current_history = 0
            # count tokens in history
            self.chat_history.reverse()
            for i in self.chat_history:
                if "prompt" in i and "response" in i:
                    tokens_batch = count_tokens(i["prompt"]) + count_tokens(i["response"])
                    if tokens_current_history + tokens_batch < settings.TOKENS_MAX_HISTORY:
                        tokens_current_history += tokens_batch
                        messages_combine.append({"role": "user", "content": i["prompt"]})
                        messages_combine.append({"role": "system", "content": i["response"]})
        messages_combine.append({"role": "user", "content": self.question})

        llm = LLMCreator.create_llm(settings.LLM_NAME, api_key=settings.API_KEY)

        completion = llm.gen_stream(model=self.gpt_model,
                                    messages=messages_combine)
        for line in completion:
            yield {"answer": str(line)}
    
    def search(self):
        return self._get_data()
        
