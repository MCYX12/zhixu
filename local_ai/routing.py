import re

MODES = ("auto", "local", "knowledge", "web", "cloud")
FRESH = re.compile(
    r"最新|今天|今日|目前|现在|实时|最近|近期|本周|本月|联网|上网|"
    r"(?:帮我|请|网上).*?(?:搜索|查找|查询)|latest|today|current|trending",
    re.IGNORECASE,
)
PRIVATE = re.compile(
    r"资料|知识库|文档|手册|nas|根据|记录|knowledge|document|manual", re.IGNORECASE
)


def route(mode: str, query: str) -> str:
    if mode in {"web", "cloud"}:
        return "disabled"
    if mode == "knowledge":
        return "knowledge"
    if FRESH.search(query):
        return "fresh_unavailable"
    if PRIVATE.search(query):
        return "knowledge"
    return "general"
