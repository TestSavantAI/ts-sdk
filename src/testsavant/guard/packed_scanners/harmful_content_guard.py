from typing import List
from testsavant.guard import InputGuard, InputPackedGuard
from testsavant.guard.input_scanners import (
    Toxicity,
    NSFW,
    Gibberish,
    BanTopics
)


class HarmfulContentGuard(InputPackedGuard):
    
    def __init__(self, allowed_topics: List[str] = [], API_KEY=None, PROJECT_ID=None, remote_addr=None, fail_fast=True):
        super().__init__(API_KEY, PROJECT_ID, remote_addr, fail_fast)
        self.add_scanner(Toxicity(tag="base", threshold=0.5))
        self.add_scanner(NSFW(tag="base", threshold=0.5))
        self.add_scanner(Gibberish(tag="base", threshold=0.5))
        assert isinstance(allowed_topics, list) and all(isinstance(topic, str) for topic in allowed_topics), "allowed_topics must be a list of strings"
        if allowed_topics:
            self.add_scanner(BanTopics(tag='base', topics=allowed_topics, mode="whitelist"))

