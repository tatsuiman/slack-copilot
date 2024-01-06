import os
import re
import logging

PRIORITY = 0
DESCRIPTION = "Graphvizのコードを生成するように指示を変更"


def run(event):
    message = event["text"]
    files = []
    processed = False
    if message.find("図") != -1:
        processed = True
        message = message.replace("図", "図(graphviz)")

    event["text"] = message
    return event, files, processed
