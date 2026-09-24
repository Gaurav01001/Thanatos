#TODO: implement md path , extract its pages and return structured raw text

class MdLoader:
    def load(self, filepath):
        with open(filepath, "r" , encoding = "utf-8") as file:
            text = file.read()

        return [
            {
                "page":1,
                "text":text
            }
        ]

MDLoader = MdLoader
mdLoader = MdLoader

if __name__ == "__main__":

    loader = MdLoader()

    pages = loader.load("benchmark_data/rag_intro.md")

    print(f"Total pages: {len(pages)}")
    print("\n===== CONTENT =====")
    print(pages[0]["text"][:1000])