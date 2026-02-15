# main.py

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document

from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from langchain_openai import OpenAIEmbeddings, ChatOpenAI

emdeddings = OpenAIEmbeddings(model="text-embedding-3-small")
llm = ChatOpenAI(model="gpt-4o", temperature=0)

PERSIST_PATH = "./qdrant_db"
COLLECTION_NAME = "star-wars-scripts"


def load_star_wars_script(url, movie_title):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    script_raw = soup.find("pre").get_text()

    return Document(page_content=script_raw, metadata={"title": movie_title})


def main():
    client = QdrantClient(path=PERSIST_PATH)

    try:
        client.get_collection(collection_name=COLLECTION_NAME)
        vectorstore = QdrantVectorStore(
            collection_name=COLLECTION_NAME,
            embeddings=emdeddings,
            client=client,
        )
    except Exception:
        client.close()

        star_wars_scripts = [
            {
                "title": "Star Wars: A New Hope",
                "url": "https://www.imsdb.com/scripts/Star-Wars-A-New-Hope.html",
            },
            {
                "title": "Star Wars: The Empire Strikes Back",
                "url": "https://www.imsdb.com/scripts/Star-Wars-The-Empire-Strikes-Back.html",
            },
            {
                "title": "Star Wars: Return of the Jedi",
                "url": "https://www.imsdb.com/scripts/Star-Wars-Return-of-the-Jedi.html",
            },
        ]

        script_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2500,
            chunk_overlap=250,
            add_start_index=True,
            separators=["\nINT.", "\nEXT.", "\n\n", "\n", " ", ""],
        )

        all_chunks = []

        for script in star_wars_scripts:
            doc = load_star_wars_script(script["url"], script["title"])
            chunks = script_splitter.split_documents([doc])
            all_chunks.extend(chunks)
            print(
                f"Loaded and split script for {script['title']} into {len(chunks)} chunks."
            )

        vectorstore = QdrantVectorStore.from_documents(
            all_chunks,
            embedding=emdeddings,
            path=PERSIST_PATH,
            collection_name=COLLECTION_NAME,
        )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 15})

    template = """
    You are a Star Wars Movie Script Expert. Use ONLY the following script excerpts to answer.
    If the answer isn't in the context, say "There is no information about this in the original Star Wars scripts."

    Context:
    {context}

    Question: 
    {question}

    Answer:"""

    prompt = ChatPromptTemplate.from_template(template)

    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    print("\n--- The Star Wars Movie Expert is ready to answer your questions ---")
    while True:
        query = input("\nYou: ")
        if query.lower() in ["exit", "quit"]:
            break

        response = rag_chain.invoke(query)
        print(f"\nStar Wars Movie Expert: {response}")


if __name__ == "__main__":
    main()