class TXTLoader:
    def load(self, filepath):
        with open(filepath, "r", encoding="utf-8") as file:
            text = file.read()
        return [
            {
                "page": 1,
                "text": text
            }
        ]

txtLoader = TXTLoader



if __name__ == "__main__":

    loader = TXTLoader()

    pages = loader.load("benchmark_data/context.txt")

    print(f"Total pages: {len(pages)}")
    print("\n===== CONTENT =====")
    print(pages[0]["text"][:1000])