"""Chatbot client wrappers for Ollama and OpenAI-compatible APIs."""

from __future__ import annotations

try:
    from ollama import Client
except Exception:
    Client = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class ChatBotClient:

    def __init__(self, name="3po", model="phi3:mini", host="http://localhost:11434", headers={"x-some-header": "some-value"}):
        self.host = host
        self.name = name
        self.model = model
        if Client is None:
            self.client = None
        else:
            self.client = Client(host=self.host, headers=headers)
        self.messages = []

    def chat(self, message: str, conversation=None, system_prompt=None):
        messages = list(self.messages) if conversation is None else []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if conversation:
            messages.extend(conversation)

        messages.append({"role": "user", "content": message})

        if self.client is None:
            raise RuntimeError("Ollama client package is not installed.")

        response = self.client.chat(
            self.model,
            messages=messages,
        )
        msg = response["message"]["content"]

        self.messages = messages + [{"role": "assistant", "content": msg}]
        return msg

    def stream_chat(self, message):
        self.messages.append(
            {
                "role": "user",
                "content": message,
            }
        )
        if self.client is None:
            raise RuntimeError("Ollama client package is not installed.")
        response = self.client.chat(self.model, self.messages, stream=True)
        answer = ""
        for chunk in response:
            piece = chunk["message"]["content"]
            print(piece, end="")
            answer += piece
        self.messages.append({"role": "assistant", "content": answer})


class ChatBotClientOpenAI():
    def __init__(self, name="3po", model="phi3:mini", host="http://10.209.93.21:8000/v1", headers={"x-some-header": "some-value"}):
        self.host = host
        self.name = name
        self.model = model
        if OpenAI is None:
            self.client = None
        else:
            self.client = OpenAI(api_key="EMPTY", base_url=self.host)
        self.messages = []

    def chat(self, messages):
        if self.client is None:
            raise RuntimeError("OpenAI client package is not installed.")

        model_id = "/home/nlp/.cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B-Instruct/snapshots/7ae557604adf67be50417f59c2c2f167def9a775"

        response = self.client.chat.completions.create(
            messages=messages,
            model=model_id,
            temperature=0.3,
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    c = ChatBotClient()
    print(c.chat("Your name is Tom, and you are the learning assistant of Python programming."))
    print(c.stream_chat("What's your name and role?"))
