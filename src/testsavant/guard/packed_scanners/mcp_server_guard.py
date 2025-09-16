from testsavant.guard import InputPackedGuard
from testsavant.guard.input_scanners import PromptInjection, Gibberish, Toxicity, NSFW, Regex, Language, Code, BanSubstrings



class MCPServerGuard(InputPackedGuard):
    
    def __init__(self, API_KEY=None, PROJECT_ID=None, remote_addr=None, fail_fast=True):
        super().__init__(API_KEY, PROJECT_ID, remote_addr, fail_fast)
        self.add_scanner(PromptInjection(tag="base", threshold=0.5))
        self.add_scanner(Gibberish(tag="base", threshold=0.5))
        self.add_scanner(Toxicity(tag="base", threshold=0.5))
        self.add_scanner(NSFW(tag="base", threshold=0.5))
        self.add_scanner(Regex(tag="default"))
        self.add_scanner(BanSubstrings(tag="default"))
        self.add_scanner(Language(tag="base", valid_languages=["en"]))
    