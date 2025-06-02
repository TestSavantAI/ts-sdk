from test_savant.guard import TSGuardInput
from test_savant.guard.image_scanners import ImageTextRedactor
from test_savant.guard.input_scanners import PromptInjection
import os

long_article = open("docs/article.txt", "r").read()
print(len(long_article))

os.environ["TEST_SAVANT_API_KEY"] = "f9c18a9102aa91ba16fd4fb5061e294673718e2be82da800" 
api_key = os.environ.get("TEST_SAVANT_API_KEY")
assert api_key is not None, "Please set TEST_SAVANT_API_KEY environment variable"

ts_api = TSGuardInput(
    API_KEY=api_key,
    PROJECT_ID="b0f8c9b1-ce09-4ad0-84c5-879a124789de",
    # remote_addr="https://api.testsavant.ai"
    remote_addr="http://localhost:8080"
)

img_redactor = ImageTextRedactor(tag="base", threshold=0.5)
ts_api.add_scanner(img_redactor)

result = ts_api.scan(None, ["docs/sfw.jpg", "docs/sfw2.jpg", "docs/nsfw.jpeg"], sync_mode=True)

for scanner_name, files in result.files.items():
    ts_api.fetch_image_results(files)


import asyncio

result = asyncio.run(ts_api.scan(None, ["docs/sfw.jpg", "docs/sfw2.jpg", "docs/nsfw.jpeg"]))

for scanner_name, files in result.files.items():
    ts_api.fetch_image_results(files)




